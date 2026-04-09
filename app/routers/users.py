from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.user import User, Invitation
from app.models.tenant import Tenant
from app.schemas.user import InviteRequest, UserOut, UserRoleUpdate, AcceptInviteRequest
from app.utils.security import hash_password, generate_invite_token
from app.services.email_service import notify_invitation

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at.asc())
    )
    users = result.scalars().all()
    return [_user_to_out(u) for u in users]


@router.post("/invite", status_code=201)
async def invite_user(
    data: InviteRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if data.role not in ("agent", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role. Use 'agent' or 'admin'")

    # check if user already exists in tenant
    existing = await db.execute(
        select(User).where(User.tenant_id == user.tenant_id, User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in team")

    # check agent limit
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one()
    user_count_result = await db.execute(
        select(User).where(User.tenant_id == user.tenant_id, User.is_active == True)
    )
    current_count = len(user_count_result.scalars().all())
    if current_count >= tenant.max_agents:
        raise HTTPException(status_code=403, detail=f"Agent limit reached ({tenant.max_agents}). Upgrade your plan.")

    token = generate_invite_token()
    invitation = Invitation(
        tenant_id=user.tenant_id,
        email=data.email,
        role=data.role,
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()

    background_tasks.add_task(notify_invitation, data.email, user.name, tenant.name, token)

    return {"detail": "Invitation sent", "token": token}


@router.post("/accept-invite", status_code=201)
async def accept_invite(data: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invitation).where(
            Invitation.token == data.token,
            Invitation.accepted_at == None,
            Invitation.expires_at > datetime.utcnow(),
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")

    # check not already registered
    existing = await db.execute(
        select(User).where(User.tenant_id == invitation.tenant_id, User.email == invitation.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in team")

    new_user = User(
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role=invitation.role,
    )
    db.add(new_user)
    invitation.accepted_at = datetime.utcnow()
    await db.flush()

    return {"detail": "Account created. You can now log in."}


@router.put("/{user_id}/role", response_model=UserOut)
async def update_role(
    user_id: UUID,
    data: UserRoleUpdate,
    user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    if data.role not in ("agent", "admin", "owner"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot change own role")

    target.role = data.role
    await db.flush()
    return _user_to_out(target)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: UUID,
    user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot deactivate the owner")

    target.is_active = False
    await db.flush()
    return {"detail": "User deactivated"}


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return _user_to_out(user)


def _user_to_out(u):
    return UserOut(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )
