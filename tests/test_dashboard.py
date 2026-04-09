import pytest


async def register_and_get_token(client, email, company):
    res = await client.post("/api/auth/register", json={
        "email": email, "password": "testpasswort123",
        "name": "Test Owner", "company_name": company,
    })
    return res.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_dashboard_overview_empty(client):
    token = await register_and_get_token(client, "dash@firma.de", "Dash Firma")
    res = await client.get("/api/dashboard/overview", headers=auth(token))
    assert res.status_code == 200
    d = res.json()
    assert d["open"] == 0
    assert d["total"] == 0


@pytest.mark.asyncio
async def test_dashboard_overview_with_tickets(client):
    token = await register_and_get_token(client, "dash2@firma.de", "Dash2 Firma")

    # create tickets
    await client.post("/api/tickets", json={
        "subject": "T1", "body": "b", "customer_email": "c1@t.de",
    }, headers=auth(token))
    await client.post("/api/tickets", json={
        "subject": "T2", "body": "b", "customer_email": "c2@t.de",
    }, headers=auth(token))

    res = await client.get("/api/dashboard/overview", headers=auth(token))
    d = res.json()
    assert d["open"] == 2
    assert d["total"] == 2


@pytest.mark.asyncio
async def test_dashboard_agents(client):
    token = await register_and_get_token(client, "agents@firma.de", "Agents Firma")
    res = await client.get("/api/dashboard/agents", headers=auth(token))
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) == 1  # the owner


@pytest.mark.asyncio
async def test_dashboard_trends(client):
    token = await register_and_get_token(client, "trends@firma.de", "Trends Firma")
    res = await client.get("/api/dashboard/trends", headers=auth(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 30  # 30 days


@pytest.mark.asyncio
async def test_widget_config(client):
    await register_and_get_token(client, "wconf@firma.de", "Widget Firma")
    res = await client.get("/api/widget/widget-firma/config")
    assert res.status_code == 200
    assert res.json()["name"] == "Widget Firma"
    assert "primary_color" in res.json()


@pytest.mark.asyncio
async def test_widget_submit(client):
    await register_and_get_token(client, "wsub@firma.de", "Wsub Firma")
    res = await client.post("/api/widget/wsub-firma/tickets", json={
        "email": "widget-user@extern.de",
        "subject": "Widget Ticket",
        "body": "Gesendet vom Widget",
    })
    assert res.status_code == 201
    assert res.json()["ticket_number"] == 1


@pytest.mark.asyncio
async def test_widget_submit_invalid_slug(client):
    res = await client.post("/api/widget/nope/tickets", json={
        "email": "a@b.de", "subject": "X", "body": "Y",
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_embed_js(client):
    res = await client.get("/api/widget/embed.js")
    assert res.status_code == 200
    assert "application/javascript" in res.headers["content-type"]
    assert "data-tenant" in res.text
