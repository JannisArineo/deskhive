import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE, APP_URL
from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/api/billing", tags=["billing"])

PLANS = {
    "free":       {"name": "Free",       "price": 0,   "max_agents": 2,   "features": ["2 Agents", "Basis-Support"]},
    "pro":        {"name": "Pro",        "price": 29,  "max_agents": 10,  "features": ["10 Agents", "Email-Notifications", "Analytics", "Widget"]},
    "enterprise": {"name": "Enterprise", "price": 99,  "max_agents": 999, "features": ["Unbegrenzte Agents", "Alles aus Pro", "SLA", "Priority Support"]},
}


def get_stripe():
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
    return stripe


@router.get("/plans")
async def list_plans():
    return PLANS


@router.get("/current")
async def current_plan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    plan_info = PLANS.get(tenant.plan, PLANS["free"])
    return {
        "plan": tenant.plan,
        "name": plan_info["name"],
        "price": plan_info["price"],
        "max_agents": tenant.max_agents,
        "features": plan_info["features"],
        "stripe_subscription_id": tenant.stripe_subscription_id,
    }


@router.post("/checkout")
async def create_checkout(
    request: Request,
    user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    body = await request.json()
    plan = body.get("plan")
    if plan not in ("pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    price_id = STRIPE_PRICE_PRO if plan == "pro" else STRIPE_PRICE_ENTERPRISE
    s = get_stripe()

    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()

    # get or create stripe customer
    if not tenant.stripe_customer_id:
        customer = s.Customer.create(email=user.email, name=tenant.name, metadata={"tenant_id": str(tenant.id)})
        tenant.stripe_customer_id = customer.id
        await db.flush()

    session = s.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{APP_URL}/billing?success=1",
        cancel_url=f"{APP_URL}/billing?cancelled=1",
        metadata={"tenant_id": str(tenant.id), "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def billing_portal(
    user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()

    if not tenant.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    s = get_stripe()
    session = s.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{APP_URL}/billing",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        tenant_id = session.get("metadata", {}).get("tenant_id")
        plan = session.get("metadata", {}).get("plan", "pro")
        sub_id = session.get("subscription")

        if tenant_id:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant.plan = plan
                tenant.stripe_subscription_id = sub_id
                tenant.max_agents = PLANS[plan]["max_agents"]
                await db.flush()

    elif event["type"] in ("customer.subscription.updated",):
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        status = sub.get("status")

        result = await db.execute(select(Tenant).where(Tenant.stripe_customer_id == customer_id))
        tenant = result.scalar_one_or_none()
        if tenant and status not in ("active", "trialing"):
            tenant.plan = "free"
            tenant.max_agents = PLANS["free"]["max_agents"]
            await db.flush()

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")

        result = await db.execute(select(Tenant).where(Tenant.stripe_customer_id == customer_id))
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant.plan = "free"
            tenant.stripe_subscription_id = None
            tenant.max_agents = PLANS["free"]["max_agents"]
            await db.flush()

    return Response(status_code=200)
