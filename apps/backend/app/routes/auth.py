from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.core.auth import (
    clear_session_cookie,
    create_access_token,
    get_client_ip,
    get_current_user,
    issue_guest_pass,
    resolve_session,
    session_claims,
    session_token,
    set_session_cookie,
    verify_google_token,
)
from app.core.rate_limiter import (
    default_chat_quota,
    enforce_ip_limit,
    google_auth_limiter,
    refresh_limiter,
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
    UserSession,
)
from app.db.neon import NeonDatabase, get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/guest", response_model=GuestPassResponse)
async def create_guest_pass(
    request: Request,
    response: Response,
    payload: GuestPassRequest | None = None,
    db: NeonDatabase = Depends(get_db),
):
    """Issue 1-Click Ephemeral Guest Pass token pre-loaded with quota."""
    client_ip = get_client_ip(request)
    device_id = payload.deviceId if payload else None
    machine_id = payload.machineId if payload else None
    pass_resp, token_str, expires_in = await issue_guest_pass(db, client_ip, device_id, machine_id)
    set_session_cookie(response, token_str, expires_in)
    return pass_resp


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
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

    remaining, _resets_at = await default_chat_quota.status(user, client_ip)

    token_str, expires_in = create_access_token(data=session_claims(user))
    set_session_cookie(response, token_str, expires_in)

    return TokenResponse(
        expiresIn=expires_in,
        user=UserSession.model_validate(user),
        quotaRemaining=remaining,
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

    remaining, resets_at = await default_chat_quota.status(current_user, client_ip)

    return {
        "user": UserSession.model_validate(current_user),
        "quota": QuotaStatus(
            tokensRemaining=remaining,
            bucketCapacity=settings.GUEST_QUOTA_DEFAULT
            if current_user.is_guest
            else settings.USER_QUOTA_DEFAULT,
            resetsAt=resets_at.isoformat(),
        ),
    }


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Revoke every token issued to this user."""
    await db.bump_token_version(current_user.id)
    clear_session_cookie(response)
    return {"success": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    token: str | None = Depends(session_token),
    db: NeonDatabase = Depends(get_db),
):
    """Refresh JWT access token for currently authenticated session."""
    enforce_ip_limit(refresh_limiter, get_client_ip(request))
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    current_user, claims = await resolve_session(token, db)

    auth_time = int(claims.get("auth_time", claims.get("iat", 0)))
    session_age = datetime.now(UTC) - datetime.fromtimestamp(auth_time, UTC)
    if session_age > timedelta(days=settings.MAX_SESSION_AGE_DAYS):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    remaining, _resets_at = await default_chat_quota.status(current_user, get_client_ip(request))
    token_str, expires_in = create_access_token(
        data=session_claims(current_user, auth_time=auth_time),
    )
    set_session_cookie(response, token_str, expires_in)

    return TokenResponse(
        expiresIn=expires_in,
        user=UserSession.model_validate(current_user),
        quotaRemaining=remaining,
        bucketCapacity=settings.GUEST_QUOTA_DEFAULT
        if current_user.is_guest
        else settings.USER_QUOTA_DEFAULT,
    )
