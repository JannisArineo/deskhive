import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User, RefreshToken
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, hash_token,
)
from app.utils.slug import generate_slug

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # generate unique slug
    base_slug = generate_slug(data.company_name)
    slug = base_slug
    counter = 1
    while True:
        exists = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not exists.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    # create tenant
    tenant = Tenant(name=data.company_name, slug=slug)
    db.add(tenant)
    await db.flush()

    # check if email already used in this tenant
    existing = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # create owner user
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role="owner",
    )
    db.add(user)
    await db.flush()

    # create tokens
    access_token = create_access_token(user.id, tenant.id)
    refresh_raw, refresh_hash, refresh_expires = create_refresh_token()

    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires))

    response.set_cookie(
        key="refresh_token",
        value=refresh_raw,
        httponly=True,
        secure=False,  # True in production
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # update last login
    user.last_login_at = datetime.utcnow()

    access_token = create_access_token(user.id, user.tenant_id)
    refresh_raw, refresh_hash, refresh_expires = create_refresh_token()

    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires))

    response.set_cookie(
        key="refresh_token",
        value=refresh_raw,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_raw = request.cookies.get("refresh_token")
    if not refresh_raw:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_hash = hash_token(refresh_raw)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > datetime.utcnow(),
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # load user
    user_result = await db.execute(select(User).where(User.id == stored.user_id, User.is_active == True))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # rotate refresh token
    await db.delete(stored)
    new_access = create_access_token(user.id, user.tenant_id)
    new_refresh_raw, new_refresh_hash, new_refresh_expires = create_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_refresh_hash, expires_at=new_refresh_expires))

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_raw,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return TokenResponse(access_token=new_access)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_raw = request.cookies.get("refresh_token")
    if refresh_raw:
        token_hash = hash_token(refresh_raw)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()
        if stored:
            await db.delete(stored)

    response.delete_cookie("refresh_token", path="/api/auth")
    return {"detail": "Logged out"}
