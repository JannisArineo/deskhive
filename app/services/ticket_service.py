import secrets
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Customer, Ticket, TicketMessage


async def get_or_create_customer(db, tenant_id, email, name=None):
    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.email == email)
    )
    customer = result.scalar_one_or_none()
    if customer:
        return customer

    customer = Customer(
        tenant_id=tenant_id,
        email=email,
        name=name,
        token=secrets.token_urlsafe(32),
    )
    db.add(customer)
    await db.flush()
    return customer


async def get_next_ticket_number(db, tenant_id):
    result = await db.execute(
        select(func.coalesce(func.max(Ticket.ticket_number), 0))
        .where(Ticket.tenant_id == tenant_id)
    )
    return result.scalar() + 1


async def create_ticket(db, tenant_id, subject, body, priority, customer_email, customer_name=None, source="portal"):
    customer = await get_or_create_customer(db, tenant_id, customer_email, customer_name)
    ticket_number = await get_next_ticket_number(db, tenant_id)

    ticket = Ticket(
        tenant_id=tenant_id,
        ticket_number=ticket_number,
        customer_id=customer.id,
        subject=subject,
        status="open",
        priority=priority,
        source=source,
    )
    db.add(ticket)
    await db.flush()

    # initial message
    message = TicketMessage(
        ticket_id=ticket.id,
        author_type="customer",
        author_id=customer.id,
        body=body,
        is_internal=False,
    )
    db.add(message)
    await db.flush()

    return ticket, customer


async def list_tickets(db, tenant_id, status=None, priority=None, assigned_to=None, search=None, page=1, per_page=20):
    query = select(Ticket).where(Ticket.tenant_id == tenant_id)
    count_query = select(func.count(Ticket.id)).where(Ticket.tenant_id == tenant_id)

    if status:
        query = query.where(Ticket.status == status)
        count_query = count_query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
        count_query = count_query.where(Ticket.priority == priority)
    if assigned_to:
        query = query.where(Ticket.assigned_to == assigned_to)
        count_query = count_query.where(Ticket.assigned_to == assigned_to)
    if search:
        query = query.where(Ticket.subject.ilike(f"%{search}%"))
        count_query = count_query.where(Ticket.subject.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Ticket.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    tickets = result.scalars().all()

    return tickets, total


async def get_ticket(db, tenant_id, ticket_id):
    result = await db.execute(
        select(Ticket).where(Ticket.tenant_id == tenant_id, Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def get_ticket_messages(db, ticket_id, include_internal=True):
    query = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
    if not include_internal:
        query = query.where(TicketMessage.is_internal == False)
    query = query.order_by(TicketMessage.created_at.asc())
    result = await db.execute(query)
    return result.scalars().all()


async def add_message(db, ticket_id, author_type, author_id, body, is_internal=False):
    message = TicketMessage(
        ticket_id=ticket_id,
        author_type=author_type,
        author_id=author_id,
        body=body,
        is_internal=is_internal,
    )
    db.add(message)
    await db.flush()
    return message


async def update_ticket(db, ticket, status=None, priority=None, assigned_to=None):
    if status is not None:
        ticket.status = status
        if status in ("resolved", "closed"):
            ticket.resolved_at = datetime.utcnow()
        elif ticket.resolved_at and status not in ("resolved", "closed"):
            ticket.resolved_at = None
    if priority is not None:
        ticket.priority = priority
    if assigned_to is not None:
        ticket.assigned_to = assigned_to
    ticket.updated_at = datetime.utcnow()
    await db.flush()
    return ticket
