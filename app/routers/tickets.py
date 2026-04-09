from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.models.ticket import Customer
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketMessageCreate,
    TicketOut, TicketDetailOut, TicketListOut, TicketMessageOut,
)
from app.services.ticket_service import (
    create_ticket, list_tickets, get_ticket, get_ticket_messages,
    add_message, update_ticket, get_or_create_customer,
)
from sqlalchemy import select

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=201)
async def create(data: TicketCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket, customer = await create_ticket(
        db, user.tenant_id, data.subject, data.body, data.priority,
        data.customer_email, data.customer_name, source="agent",
    )
    return _ticket_to_out(ticket, customer)


@router.get("", response_model=TicketListOut)
async def list_all(
    status: str = Query(None),
    priority: str = Query(None),
    assigned_to: UUID = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tickets, total = await list_tickets(db, user.tenant_id, status, priority, assigned_to, search, page, per_page)

    items = []
    for t in tickets:
        customer = await _get_customer(db, t.customer_id)
        items.append(_ticket_to_out(t, customer))

    return TicketListOut(tickets=items, total=total, page=page, per_page=per_page)


@router.get("/{ticket_id}", response_model=TicketDetailOut)
async def detail(ticket_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await get_ticket(db, user.tenant_id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages = await get_ticket_messages(db, ticket.id)
    customer = await _get_customer(db, ticket.customer_id)

    out = _ticket_to_out(ticket, customer)
    return TicketDetailOut(
        **out.model_dump(),
        messages=[_msg_to_out(m) for m in messages],
    )


@router.put("/{ticket_id}", response_model=TicketOut)
async def update(ticket_id: UUID, data: TicketUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await get_ticket(db, user.tenant_id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = await update_ticket(db, ticket, data.status, data.priority, data.assigned_to)
    customer = await _get_customer(db, ticket.customer_id)
    return _ticket_to_out(ticket, customer)


@router.get("/{ticket_id}/messages", response_model=list[TicketMessageOut])
async def messages(ticket_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await get_ticket(db, user.tenant_id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msgs = await get_ticket_messages(db, ticket.id)
    return [_msg_to_out(m) for m in msgs]


@router.post("/{ticket_id}/messages", response_model=TicketMessageOut, status_code=201)
async def add_reply(ticket_id: UUID, data: TicketMessageCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await get_ticket(db, user.tenant_id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = await add_message(db, ticket.id, "agent", user.id, data.body, data.is_internal)

    # auto-set to in_progress if still open
    if ticket.status == "open" and not data.is_internal:
        await update_ticket(db, ticket, status="in_progress")

    return _msg_to_out(msg)


async def _get_customer(db, customer_id):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    return result.scalar_one_or_none()


def _msg_to_out(m):
    return TicketMessageOut(
        id=str(m.id),
        author_type=m.author_type,
        author_id=str(m.author_id),
        body=m.body,
        is_internal=m.is_internal,
        created_at=m.created_at,
    )


def _ticket_to_out(ticket, customer):
    return TicketOut(
        id=str(ticket.id),
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        source=ticket.source,
        customer_email=customer.email if customer else None,
        customer_name=customer.name if customer else None,
        assigned_to=str(ticket.assigned_to) if ticket.assigned_to else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
    )
