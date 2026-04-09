from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.tenant import Tenant
from app.models.ticket import Customer, Ticket, TicketMessage
from app.services.ticket_service import (
    create_ticket, get_or_create_customer, get_ticket_messages, add_message,
)

router = APIRouter(prefix="/api/portal", tags=["portal"])


class PortalTicketCreate(BaseModel):
    email: str
    name: str | None = None
    subject: str
    body: str
    priority: str = "medium"


class PortalReply(BaseModel):
    body: str


async def _get_tenant_by_slug(slug, db):
    result = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return tenant


async def _get_customer_by_token(token, db):
    result = await db.execute(select(Customer).where(Customer.token == token))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid token")
    return customer


@router.get("/{slug}/info")
async def portal_info(slug: str, db: AsyncSession = Depends(get_db)):
    tenant = await _get_tenant_by_slug(slug, db)
    return {
        "name": tenant.name,
        "slug": tenant.slug,
        "settings": tenant.settings or {},
    }


@router.post("/{slug}/tickets", status_code=201)
async def submit_ticket(slug: str, data: PortalTicketCreate, db: AsyncSession = Depends(get_db)):
    tenant = await _get_tenant_by_slug(slug, db)

    ticket, customer = await create_ticket(
        db, tenant.id, data.subject, data.body, data.priority,
        data.email, data.name, source="portal",
    )

    return {
        "ticket_id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "customer_token": customer.token,
    }


@router.get("/{slug}/tickets")
async def list_customer_tickets(slug: str, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    tenant = await _get_tenant_by_slug(slug, db)
    customer = await _get_customer_by_token(token, db)

    if customer.tenant_id != tenant.id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Ticket)
        .where(Ticket.tenant_id == tenant.id, Ticket.customer_id == customer.id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()

    return [{
        "id": str(t.id),
        "ticket_number": t.ticket_number,
        "subject": t.subject,
        "status": t.status,
        "priority": t.priority,
        "created_at": t.created_at.isoformat(),
    } for t in tickets]


@router.get("/{slug}/tickets/{ticket_id}")
async def get_customer_ticket(slug: str, ticket_id: str, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    tenant = await _get_tenant_by_slug(slug, db)
    customer = await _get_customer_by_token(token, db)

    result = await db.execute(
        select(Ticket).where(Ticket.id == UUID(ticket_id), Ticket.tenant_id == tenant.id, Ticket.customer_id == customer.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages = await get_ticket_messages(db, ticket.id, include_internal=False)

    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat(),
        "messages": [{
            "author_type": m.author_type,
            "body": m.body,
            "created_at": m.created_at.isoformat(),
        } for m in messages],
    }


@router.post("/{slug}/tickets/{ticket_id}/reply")
async def customer_reply(slug: str, ticket_id: str, data: PortalReply, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    tenant = await _get_tenant_by_slug(slug, db)
    customer = await _get_customer_by_token(token, db)

    result = await db.execute(
        select(Ticket).where(Ticket.id == UUID(ticket_id), Ticket.tenant_id == tenant.id, Ticket.customer_id == customer.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = await add_message(db, ticket.id, "customer", customer.id, data.body)

    # reopen if resolved
    if ticket.status in ("resolved", "closed"):
        ticket.status = "open"
        await db.flush()

    return {"detail": "Reply sent"}
