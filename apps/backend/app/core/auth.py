import asyncio
import hashlib
import ipaddress
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, Request, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.rate_limiter import default_chat_quota, guest_signup_limiter
from app.core.security_events import security_event
from app.db.models import GuestPassResponse, User, UserSession
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
            if len(parts) >= n and _valid_ip(parts[-n]):
                return parts[-n]
    socket_ip = request.client.host if request.client else "127.0.0.1"
    return socket_ip if _valid_ip(socket_ip) else "127.0.0.1"


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


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


def hash_device_id(device_id: str) -> str:
    """SHA-256 hash of device_id, so the raw credential is never stored or exposed."""
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=not settings.is_dev,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.SESSION_COOKIE_NAME,
        path="/",
        secure=not settings.is_dev,
        httponly=True,
        samesite="lax",
    )


# The raw id lives only in this cookie. The database stores its SHA-256 hash.
DEVICE_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
_DEVICE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def new_device_id() -> str:
    return secrets.token_urlsafe(32)


def valid_device_id(value: str | None) -> bool:
    """True when the cookie value is long enough to be unguessable and safe to hash."""
    if value is None or not 32 <= len(value) <= 128:
        return False
    return set(value) <= _DEVICE_ID_CHARS


def set_device_cookie(response: Response, device_id: str) -> None:
    response.set_cookie(
        settings.DEVICE_COOKIE_NAME,
        device_id,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.is_dev,
        samesite="lax",
        path="/",
    )


async def session_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> str | None:
    return request.cookies.get(settings.SESSION_COOKIE_NAME) or (
        credentials.credentials if credentials else None
    )


async def resolve_session(token: str, db: NeonDatabase) -> tuple[User, dict]:
    """Decode the token and load its user (with the token claims); 401 if bad or signed out."""
    payload = decode_access_token(token)
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
    request: Request,
    token: str | None = Depends(session_token),
    db: NeonDatabase = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and verify authenticated user."""
    if not token:
        raise _unauthorized("Authentication credentials were not provided")
    try:
        user, _claims = await resolve_session(token, db)
    except HTTPException:
        security_event("auth.failure", reason="session", ip=get_client_ip(request))
        raise
    await db.touch_user(user.id)
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_guest or not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only.")
    return current_user


async def get_current_user_optional(
    request: Request,
    token: str | None = Depends(session_token),
    db: NeonDatabase = Depends(get_db),
) -> User | None:
    """Optional user extractor for endpoints supporting anonymous sessions."""
    if not token:
        return None
    try:
        return (await resolve_session(token, db))[0]
    except HTTPException:
        security_event("auth.failure", reason="session", ip=get_client_ip(request))
        return None


async def issue_guest_pass(
    db: NeonDatabase,
    client_ip: str,
    device_id: str | None = None,
    machine_id: str | None = None,
) -> tuple[GuestPassResponse, str, int, str]:
    """Issue or retrieve a guest pass.

    ``device_id`` is the raw HttpOnly cookie value, never a client-supplied body field.
    Returns the response, session token, token lifetime, and the raw device id to set.
    """
    now = datetime.now(UTC)
    raw_device_id = device_id if valid_device_id(device_id) else new_device_id()
    hashed_device_id = hash_device_id(raw_device_id)

    clean_machine_id = machine_id.strip() if machine_id and machine_id.strip() else None
    hashed_machine_id = hash_device_id(clean_machine_id) if clean_machine_id else None

    target_user: User | None = await db.get_guest_by_device(hashed_device_id)

    if target_user:
        await db.update_user_last_seen(
            target_user.id,
            client_ip=client_ip,
            device_id=hashed_device_id,
            machine_hash=hashed_machine_id,
        )
        target_user.client_ip = client_ip
        if hashed_machine_id and not target_user.machine_hash:
            target_user.machine_hash = hashed_machine_id
        target_user.last_seen_at = now
    else:
        if db.pool is not None:
            recent = await db.count_guest_signups(client_ip)
            if recent >= settings.GUEST_SIGNUPS_PER_IP_PER_HOUR:
                security_event("quota.exceeded", ip=client_ip, kind="guest_signup")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many guest sessions from this network. Try again later.",
                    headers={"Retry-After": "3600"},
                )
        if not guest_signup_limiter.hit(client_ip):
            security_event("quota.exceeded", ip=client_ip, kind="guest_signup")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many guest sessions from this network. Try again later.",
                headers={"Retry-After": "3600"},
            )
        assigned_device_id = hashed_device_id
        guest_uuid = uuid4()
        guest_name = f"Guest User #{str(guest_uuid)[:6]}"
        user = User(
            id=guest_uuid,
            email=None,
            name=guest_name,
            avatar_url=None,
            is_guest=True,
            client_ip=client_ip,
            device_id=assigned_device_id,
            machine_hash=hashed_machine_id,
            created_at=now,
            last_seen_at=now,
        )
        target_user = await db.create_user(user)

    tokens_remaining, _resets_at = await default_chat_quota.status(
        user=target_user,
        client_ip=client_ip,
    )

    token_str, expires_in = create_access_token(data=session_claims(target_user))

    response = GuestPassResponse(
        user=UserSession.model_validate(target_user),
        expiresIn=expires_in,
        quotaRemaining=tokens_remaining,
        bucketCapacity=settings.GUEST_QUOTA_DEFAULT,
    )
    return response, token_str, expires_in, raw_device_id


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
