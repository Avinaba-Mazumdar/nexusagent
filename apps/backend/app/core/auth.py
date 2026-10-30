import asyncio
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.rate_limiter import default_rate_limiter, guest_signup_limiter
from app.db.models import AuthTokens, GuestPassResponse, User, UserSession
from app.db.neon import NeonDatabase, get_db

logger = logging.getLogger("nexusagent.core.auth")

security_bearer = HTTPBearer(auto_error=False)


def get_client_ip(request: Request, hops: int | None = None) -> str:
    """
    Extract the client IP used for rate-limit keying.

    With ``TRUSTED_PROXY_HOPS = 0`` (default) this is the socket address, so a client cannot rotate
    quota by sending its own ``X-Forwarded-For``. Behind ``n`` trusted proxies each proxy appends the
    address it saw, so the client is the ``n``-th entry from the right; entries further left are
    client-controlled and never used.
    """
    n = settings.TRUSTED_PROXY_HOPS if hops is None else hops
    if n > 0:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if len(parts) >= n:
                return parts[-n]
    return request.client.host if request.client else "127.0.0.1"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, int]:
    """Create signed HS256 JWT access token, returning token and expiresIn seconds."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = datetime.now(UTC) + timedelta(seconds=expires_in)

    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, expires_in


def decode_access_token(token: str) -> dict:
    """Decode and validate signed JWT."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def session_claims(user: User, auth_time: int | None = None) -> dict:
    """Claims identifying a session: who, which token generation, and when the login happened."""
    return {
        "sub": str(user.id),
        "tv": user.token_version,
        "auth_time": auth_time if auth_time is not None else int(datetime.now(UTC).timestamp()),
    }


def user_to_session(user: User) -> UserSession:
    """Convert User model to UserSession contract schema."""
    return UserSession(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatarUrl=user.avatar_url,
        isGuest=user.is_guest,
        createdAt=user.created_at.isoformat(),
        lastSeenAt=user.last_seen_at.isoformat(),
    )


def hash_device_id(device_id: str) -> str:
    """SHA-256 hash of device_id, so the raw credential is never stored or exposed."""
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def resolve_session(
    credentials: HTTPAuthorizationCredentials, db: NeonDatabase
) -> tuple[User, dict]:
    """Decode the bearer token and load its user (with the token claims); 401 if bad or signed out."""
    payload = decode_access_token(credentials.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized("Invalid token subject")

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        raise _unauthorized("Malformed token user ID")

    user = await db.get_user_by_id(user_uuid)
    if not user:
        raise _unauthorized("User not found")
    if payload.get("tv", 0) != user.token_version:
        raise _unauthorized("Session has been signed out")
    return user, payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
    db: NeonDatabase = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and verify authenticated user."""
    if not credentials:
        raise _unauthorized("Authentication credentials were not provided")
    user, _claims = await resolve_session(credentials, db)
    await db.touch_user(user.id)
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
    db: NeonDatabase = Depends(get_db),
) -> User | None:
    """Optional user extractor for endpoints supporting anonymous sessions."""
    if not credentials:
        return None
    try:
        return (await resolve_session(credentials, db))[0]
    except HTTPException:
        return None


async def issue_guest_pass(
    db: NeonDatabase, client_ip: str, device_id: str | None = None
) -> GuestPassResponse:
    """Issue or retrieve 1-Click Guest Pass token bound to client IP & device ID."""
    now = datetime.now(UTC)
    clean_device_id = device_id.strip() if device_id and device_id.strip() else None
    hashed_device_id = hash_device_id(clean_device_id) if clean_device_id else None

    target_user: User | None = None
    if hashed_device_id:
        target_user = await db.get_guest_by_device_id(hashed_device_id)

    if target_user:
        await db.update_user_last_seen(
            target_user.id, client_ip=client_ip, device_id=hashed_device_id
        )
        target_user.client_ip = client_ip
        target_user.last_seen_at = now
    else:
        if not guest_signup_limiter.hit(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many guest sessions from this network. Try again later.",
                headers={"Retry-After": "3600"},
            )
        assigned_device_id = hashed_device_id or hash_device_id(uuid4().hex)
        guest_uuid = uuid4()
        guest_name = f"Guest Architect #{str(guest_uuid)[:6]}"
        user = User(
            id=guest_uuid,
            email=None,
            name=guest_name,
            avatar_url=None,
            is_guest=True,
            client_ip=client_ip,
            device_id=assigned_device_id,
            created_at=now,
            last_seen_at=now,
        )
        target_user = await db.create_user(user)

    tokens_remaining = await default_rate_limiter.get_quota(
        user_id=target_user.id,
        is_guest=True,
    )

    token_str, expires_in = create_access_token(data=session_claims(target_user))

    return GuestPassResponse(
        user=user_to_session(target_user),
        tokens=AuthTokens(
            accessToken=token_str,
            tokenType="bearer",
            expiresIn=expires_in,
        ),
        quotaRemaining=tokens_remaining,
        bucketCapacity=settings.GUEST_QUOTA_DEFAULT,
    )


GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]

# Google's signing keys, cached for an hour; ID tokens are verified locally against them.
_google_jwks = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)


def _google_unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token's signature, audience, issuer and expiry; return the profile."""
    try:
        signing_key = await asyncio.to_thread(_google_jwks.get_signing_key_from_jwt, credential)
        info = jwt.decode(
            credential,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        logger.warning("Google signing keys unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication service unreachable",
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise _google_unauthorized("Google token audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise _google_unauthorized("Google token issuer mismatch") from exc
    except jwt.PyJWTError as exc:
        raise _google_unauthorized("Invalid or expired Google credential") from exc

    email = info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile does not contain an email address",
        )
    if str(info.get("email_verified")).lower() not in ("true", "1"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email address has not been verified",
        )

    return {
        "email": email,
        "name": info.get("name") or email.split("@")[0],
        "picture": info.get("picture"),
        "sub": info["sub"],
    }
