from datetime import timedelta

from fastapi import APIRouter, Depends, Request

from app.config import settings
from app.core.auth import (
    create_access_token,
    get_client_ip,
    get_current_user,
    issue_guest_pass,
    user_to_session,
    verify_google_token,
)
from app.core.rate_limiter import default_rate_limiter
from app.db.models import (
    GoogleAuthRequest,
    GuestPassRequest,
    GuestPassResponse,
    QuotaStatus,
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
    google_profile = await verify_google_token(payload.credential)

    client_ip = get_client_ip(request)
    user = await db.upsert_google_user(
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
        data={"sub": str(user.id), "role": "user", "is_guest": False},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(
        accessToken=token_str,
        tokenType="bearer",
        expiresIn=expires_in,
        user=user_to_session(user),
        quotaRemaining=tokens_remaining,
        bucketCapacity=settings.USER_QUOTA_DEFAULT,
    )


@router.get("/me")
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Return active user profile and quota bucket status."""
    client_ip = get_client_ip(request)
    await db.update_user_last_seen(current_user.id, client_ip)
    current_user.client_ip = client_ip

    tokens_remaining = await default_rate_limiter.get_quota(
        user_id=current_user.id,
        is_guest=current_user.is_guest,
    )

    return {
        "user": user_to_session(current_user),
        "quota": QuotaStatus(
            tokensRemaining=tokens_remaining,
            bucketCapacity=settings.GUEST_QUOTA_DEFAULT
            if current_user.is_guest
            else settings.USER_QUOTA_DEFAULT,
            resetMinutes=60,
        ),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Refresh JWT access token for currently authenticated session."""
    tokens_remaining = await default_rate_limiter.get_quota(
        user_id=current_user.id,
        is_guest=current_user.is_guest,
    )

    token_str, expires_in = create_access_token(
        data={
            "sub": str(current_user.id),
            "role": "guest" if current_user.is_guest else "user",
            "is_guest": current_user.is_guest,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
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
