from fastapi import BackgroundTasks

from app.utils.email import send_email, ticket_created_email, ticket_reply_email, invite_email
from app.config import APP_URL


async def notify_ticket_created(customer_email, customer_name, ticket_number, subject, tenant_slug, customer_token):
    portal_url = f"{APP_URL}/portal/{tenant_slug}/track"
    email_data = ticket_created_email(customer_email, customer_name, ticket_number, subject, portal_url, customer_token)
    await send_email(**email_data)


async def notify_ticket_reply(customer_email, customer_name, ticket_number, subject, reply_body, tenant_slug, customer_token):
    portal_url = f"{APP_URL}/portal/{tenant_slug}/track"
    email_data = ticket_reply_email(customer_email, customer_name, ticket_number, subject, reply_body, portal_url, customer_token)
    await send_email(**email_data)


async def notify_invitation(email, inviter_name, tenant_name, invite_token):
    invite_url = f"{APP_URL}/invite/{invite_token}"
    email_data = invite_email(email, inviter_name, tenant_name, invite_url)
    await send_email(**email_data)
