import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL

logger = logging.getLogger(__name__)


async def send_email(to, subject, body_text, body_html=None):
    if not SMTP_HOST or not SMTP_USER:
        logger.warning(f"Email not configured, skipping: {subject} -> {to}")
        return False

    try:
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email sent: {subject} -> {to}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {subject} -> {to}: {e}")
        return False


def ticket_created_email(customer_email, customer_name, ticket_number, subject, portal_url, token):
    name = customer_name or customer_email
    return {
        "to": customer_email,
        "subject": f"[#{ticket_number}] {subject} - Ticket erstellt",
        "body_text": (
            f"Hallo {name},\n\n"
            f"dein Ticket #{ticket_number} \"{subject}\" wurde erstellt.\n\n"
            f"Du kannst den Status hier verfolgen:\n"
            f"{portal_url}?token={token}\n\n"
            f"Viele Gruesse,\nDas Support-Team"
        ),
    }


def ticket_reply_email(customer_email, customer_name, ticket_number, subject, reply_body, portal_url, token):
    name = customer_name or customer_email
    return {
        "to": customer_email,
        "subject": f"Re: [#{ticket_number}] {subject}",
        "body_text": (
            f"Hallo {name},\n\n"
            f"es gibt eine neue Antwort zu deinem Ticket #{ticket_number}:\n\n"
            f"---\n{reply_body}\n---\n\n"
            f"Antworten: {portal_url}?token={token}\n\n"
            f"Viele Gruesse,\nDas Support-Team"
        ),
    }


def invite_email(email, inviter_name, tenant_name, invite_url):
    return {
        "to": email,
        "subject": f"Einladung: {tenant_name} auf DeskHive",
        "body_text": (
            f"Hallo,\n\n"
            f"{inviter_name} hat dich zu {tenant_name} auf DeskHive eingeladen.\n\n"
            f"Klicke hier um die Einladung anzunehmen:\n"
            f"{invite_url}\n\n"
            f"Viele Gruesse,\nDeskHive"
        ),
    }
