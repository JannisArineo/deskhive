from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class TicketCreate(BaseModel):
    subject: str
    body: str
    priority: str = "medium"
    customer_email: str
    customer_name: str | None = None


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None


class TicketMessageCreate(BaseModel):
    body: str
    is_internal: bool = False


class TicketMessageOut(BaseModel):
    id: UUID
    author_type: str
    author_id: UUID
    body: str
    is_internal: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: UUID
    ticket_number: int
    subject: str
    status: str
    priority: str
    source: str
    customer_email: str | None = None
    customer_name: str | None = None
    assigned_to: UUID | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    class Config:
        from_attributes = True


class TicketDetailOut(TicketOut):
    messages: list[TicketMessageOut] = []


class TicketListOut(BaseModel):
    tickets: list[TicketOut]
    total: int
    page: int
    per_page: int
