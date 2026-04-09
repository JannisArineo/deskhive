from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, JSON, Uuid
from uuid_utils import uuid7

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Uuid, primary_key=True, default=uuid7)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    plan = Column(String(50), nullable=False, default="free")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    settings = Column(JSON, nullable=False, default=dict)
    max_agents = Column(Integer, nullable=False, default=2)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
