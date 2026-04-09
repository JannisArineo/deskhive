from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey, Index, Uuid
from uuid_utils import uuid7

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Uuid, primary_key=True, default=uuid7)
    tenant_id = Column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_customers_tenant_email", "tenant_id", "email", unique=True),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Uuid, primary_key=True, default=uuid7)
    tenant_id = Column(Uuid, ForeignKey("tenants.id"), nullable=False)
    ticket_number = Column(Integer, nullable=False)
    customer_id = Column(Uuid, ForeignKey("customers.id"), nullable=False)
    assigned_to = Column(Uuid, ForeignKey("users.id"), nullable=True)
    subject = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="open")
    priority = Column(String(50), nullable=False, default="medium")
    source = Column(String(50), nullable=False, default="portal")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_tickets_tenant_status", "tenant_id", "status"),
        Index("ix_tickets_tenant_assigned", "tenant_id", "assigned_to"),
        Index("ix_tickets_tenant_number", "tenant_id", "ticket_number", unique=True),
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(Uuid, primary_key=True, default=uuid7)
    ticket_id = Column(Uuid, ForeignKey("tickets.id"), nullable=False, index=True)
    author_type = Column(String(50), nullable=False)
    author_id = Column(Uuid, nullable=False)
    body = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
