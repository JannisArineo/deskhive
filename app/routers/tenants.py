from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


@router.get("/current")
async def get_current_tenant(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "max_agents": tenant.max_agents,
        "settings": tenant.settings or {},
    }


@router.put("/current")
async def update_current_tenant(
    data: TenantUpdate,
    user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()

    if data.name is not None:
        tenant.name = data.name
    if data.settings is not None:
        tenant.settings = {**(tenant.settings or {}), **data.settings}

    await db.flush()
    return {"detail": "Updated", "name": tenant.name, "settings": tenant.settings}
