from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.core.auth import (
    create_access_token,
    decode_access_token,
    get_client_ip,
    get_current_user,
    issue_guest_pass,
    security_bearer,
    session_claims,
    token_lifetime,
    user_to_session,
    verify_google_token,
)
from app.core.rate_limiter import (
    default_rate_limiter,
    enforce_ip_limit,
    google_auth_limiter,
    refresh_limiter,
    resets_at,
)
from app.db.models import (
    GoogleAuthRequest,
    GuestPassRequest,
    GuestPassResponse,
    MeResponse,
    QuotaStatus,
    SuccessResponse,
    TokenResponse,
    User,
)
from app.db.neon import NeonDatabase, get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/guest", response_model=GuestPassResponse)
async def create_guest_pass(
    request: Request,
    payload: GuestPassRequest | None = None,
    db: NeonDatabase = Depends(get_db),
):
    """Issue 1-Click Ephemeral Guest Pass token pre-loaded with quota."""
    client_ip = get_client_ip(request)
    device_id = payload.deviceId if payload else None
    return await issue_guest_pass(db, client_ip, device_id)


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    db: NeonDatabase = Depends(get_db),
):
    """Authenticate or register user via verified Google ID token."""
    client_ip = get_client_ip(request)
    enforce_ip_limit(google_auth_limiter, client_ip)
    google_profile = await verify_google_token(payload.credential)

    user = await db.upsert_google_user(
        google_sub=google_profile["sub"],
        email=google_profile["email"],
        name=google_profile["name"],
        avatar_url=google_profile.get("picture"),
        client_ip=client_ip,
    )

    tokens_remaining = await default_rate_limiter.get_quota(
        user_id=user.id,
        is_guest=False,
    )

    token_str, expires_in = create_access_token(
        data=session_claims(user), expires_delta=token_lifetime(user)
    )

    return TokenResponse(
        accessToken=token_str,
        tokenType="bearer",
        expiresIn=expires_in,
        user=user_to_session(user),
        quotaRemaining=tokens_remaining,
        bucketCapacity=settings.USER_QUOTA_DEFAULT,
    )


@router.get("/me", response_model=MeResponse)
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Return active user profile and quota bucket status."""
    client_ip = get_client_ip(request)
    await db.update_user_last_seen(current_user.id, client_ip)
    current_user.client_ip = client_ip

    bucket = await default_rate_limiter.get_bucket(
        user_id=current_user.id,
        is_guest=current_user.is_guest,
    )

    return {
        "user": user_to_session(current_user),
        "quota": QuotaStatus(
            tokensRemaining=bucket.tokens_remaining,
            bucketCapacity=settings.GUEST_QUOTA_DEFAULT
            if current_user.is_guest
            else settings.USER_QUOTA_DEFAULT,
            resetsAt=resets_at(bucket).isoformat(),
        ),
    }


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Revoke every token issued to this user."""
    await db.bump_token_version(current_user.id)
    return {"success": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security_bearer),
    current_user: User = Depends(get_current_user),
):
    """Refresh JWT access token for currently authenticated session."""
    tokens_remaining = await default_rate_limiter.get_quota(
        user_id=current_user.id,
        is_guest=current_user.is_guest,
    )

    enforce_ip_limit(refresh_limiter, get_client_ip(request))
    payload = decode_access_token(credentials.credentials)
    auth_time = int(payload.get("auth_time", payload.get("iat", 0)))
    session_age = datetime.now(UTC) - datetime.fromtimestamp(auth_time, UTC)
    if session_age > timedelta(days=settings.MAX_SESSION_AGE_DAYS):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_str, expires_in = create_access_token(
        data=session_claims(current_user, auth_time=auth_time),
        expires_delta=token_lifetime(current_user),
    )

    return TokenResponse(
        accessToken=token_str,
        tokenType="bearer",
        expiresIn=expires_in,
        user=user_to_session(current_user),
        quotaRemaining=tokens_remaining,
        bucketCapacity=settings.GUEST_QUOTA_DEFAULT
        if current_user.is_guest
        else settings.USER_QUOTA_DEFAULT,
    )
