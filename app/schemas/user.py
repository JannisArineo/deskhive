from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "agent"


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: str


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str
