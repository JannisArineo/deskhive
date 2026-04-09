from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.tenant import Tenant
from app.services.ticket_service import create_ticket
from app.config import APP_URL

router = APIRouter(prefix="/api/widget", tags=["widget"])


class WidgetTicketCreate(BaseModel):
    email: str
    name: str | None = None
    subject: str
    body: str


@router.get("/{slug}/config")
async def widget_config(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Not found")

    settings = tenant.settings or {}
    return {
        "name": tenant.name,
        "primary_color": settings.get("primary_color", "#6366f1"),
        "greeting": settings.get("widget_greeting", "Wie koennen wir helfen?"),
    }


@router.post("/{slug}/tickets", status_code=201)
async def widget_submit(slug: str, data: WidgetTicketCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Not found")

    ticket, customer = await create_ticket(
        db, tenant.id, data.subject, data.body, "medium",
        data.email, data.name, source="widget",
    )

    return {
        "ticket_number": ticket.ticket_number,
        "message": "Ticket erstellt! Wir melden uns.",
    }


@router.get("/embed.js")
async def embed_js():
    js = f"""
(function() {{
    var tenant = document.currentScript.getAttribute('data-tenant');
    if (!tenant) return;
    var API = '{APP_URL}/api/widget';

    // Create button
    var btn = document.createElement('div');
    btn.innerHTML = '&#x1f4ac;';
    btn.style.cssText = 'position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;background:#6366f1;color:white;display:flex;align-items:center;justify-content:center;font-size:24px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:99999;';
    document.body.appendChild(btn);

    // Create iframe container
    var container = document.createElement('div');
    container.style.cssText = 'position:fixed;bottom:90px;right:20px;width:380px;max-height:500px;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.2);background:white;z-index:99999;display:none;overflow:hidden;';
    container.innerHTML = '<div style="padding:16px;">'
        + '<h3 style="margin:0 0 4px 0;font-size:16px;">Support</h3>'
        + '<p style="margin:0 0 12px 0;color:#666;font-size:13px;">Wie koennen wir helfen?</p>'
        + '<form id="dh-widget-form">'
        + '<input type="email" placeholder="Deine E-Mail" required style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px;box-sizing:border-box;">'
        + '<input type="text" placeholder="Betreff" required style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px;box-sizing:border-box;">'
        + '<textarea placeholder="Beschreibung" required rows="3" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px;box-sizing:border-box;resize:vertical;"></textarea>'
        + '<button type="submit" style="width:100%;padding:10px;background:#6366f1;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;">Senden</button>'
        + '</form>'
        + '<div id="dh-widget-success" style="display:none;text-align:center;padding:20px 0;">'
        + '<p style="font-size:18px;margin:0;">&#x2705;</p>'
        + '<p style="margin:8px 0 0 0;">Ticket erstellt! Wir melden uns.</p>'
        + '</div>'
        + '</div>';
    document.body.appendChild(container);

    btn.addEventListener('click', function() {{
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
    }});

    // Load config
    fetch(API + '/' + tenant + '/config').then(r => r.json()).then(cfg => {{
        btn.style.background = cfg.primary_color;
        container.querySelector('h3').textContent = cfg.name + ' Support';
        container.querySelector('p').textContent = cfg.greeting;
        container.querySelector('button').style.background = cfg.primary_color;
    }}).catch(function() {{}});

    // Form submit
    container.querySelector('form').addEventListener('submit', function(e) {{
        e.preventDefault();
        var inputs = e.target.querySelectorAll('input, textarea');
        var data = {{email: inputs[0].value, subject: inputs[1].value, body: inputs[2].value}};

        fetch(API + '/' + tenant + '/tickets', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(data),
        }}).then(function(r) {{
            if (r.ok) {{
                e.target.style.display = 'none';
                document.getElementById('dh-widget-success').style.display = 'block';
                setTimeout(function() {{
                    container.style.display = 'none';
                    e.target.style.display = 'block';
                    document.getElementById('dh-widget-success').style.display = 'none';
                    e.target.reset();
                }}, 3000);
            }}
        }});
    }});
}})();
"""
    return Response(content=js, media_type="application/javascript")
