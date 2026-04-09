from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.models.ticket import Ticket, TicketMessage

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tid = user.tenant_id
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # counts by status
    result = await db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.tenant_id == tid)
        .group_by(Ticket.status)
    )
    status_counts = dict(result.all())

    # resolved today
    resolved_today = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.tenant_id == tid, Ticket.resolved_at >= today)
    )

    # total tickets
    total = sum(status_counts.values())

    # avg first response time (time between ticket creation and first agent message)
    # simplified: just count tickets with at least one agent reply
    tickets_with_reply = await db.execute(
        select(func.count(func.distinct(TicketMessage.ticket_id)))
        .join(Ticket, Ticket.id == TicketMessage.ticket_id)
        .where(Ticket.tenant_id == tid, TicketMessage.author_type == "agent")
    )

    return {
        "open": status_counts.get("open", 0),
        "in_progress": status_counts.get("in_progress", 0),
        "waiting": status_counts.get("waiting", 0),
        "resolved": status_counts.get("resolved", 0),
        "closed": status_counts.get("closed", 0),
        "resolved_today": resolved_today.scalar() or 0,
        "total": total,
        "tickets_with_reply": tickets_with_reply.scalar() or 0,
    }


@router.get("/agents")
async def agent_workload(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tid = user.tenant_id

    # tickets per agent (only open/in_progress)
    result = await db.execute(
        select(User.id, User.name, func.count(Ticket.id).label("ticket_count"))
        .outerjoin(Ticket, and_(
            Ticket.assigned_to == User.id,
            Ticket.status.in_(["open", "in_progress"]),
        ))
        .where(User.tenant_id == tid, User.is_active == True)
        .group_by(User.id, User.name)
        .order_by(func.count(Ticket.id).desc())
    )

    agents = []
    for row in result.all():
        agents.append({
            "id": str(row[0]),
            "name": row[1],
            "open_tickets": row[2],
        })

    return agents


@router.get("/trends")
async def trends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tid = user.tenant_id
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # created per day (last 30 days)
    result = await db.execute(
        select(
            func.date(Ticket.created_at).label("day"),
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.tenant_id == tid, Ticket.created_at >= thirty_days_ago)
        .group_by(func.date(Ticket.created_at))
        .order_by(text("day"))
    )
    created = {str(row[0]): row[1] for row in result.all()}

    # resolved per day
    result = await db.execute(
        select(
            func.date(Ticket.resolved_at).label("day"),
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.tenant_id == tid, Ticket.resolved_at >= thirty_days_ago)
        .group_by(func.date(Ticket.resolved_at))
        .order_by(text("day"))
    )
    resolved = {str(row[0]): row[1] for row in result.all()}

    # build 30-day array
    days = []
    for i in range(30):
        day = (thirty_days_ago + timedelta(days=i)).strftime("%Y-%m-%d")
        days.append({
            "date": day,
            "created": created.get(day, 0),
            "resolved": resolved.get(day, 0),
        })

    return days
