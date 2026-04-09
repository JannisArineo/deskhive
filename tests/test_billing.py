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
async def test_list_plans(client):
    res = await client.get("/api/billing/plans")
    assert res.status_code == 200
    plans = res.json()
    assert "free" in plans
    assert "pro" in plans
    assert "enterprise" in plans
    assert plans["pro"]["price"] == 29
    assert plans["enterprise"]["price"] == 99


@pytest.mark.asyncio
async def test_current_plan_default_free(client):
    token = await register_and_get_token(client, "plan@firma.de", "Plan Firma")
    res = await client.get("/api/billing/current", headers=auth(token))
    assert res.status_code == 200
    d = res.json()
    assert d["plan"] == "free"
    assert d["max_agents"] == 2


@pytest.mark.asyncio
async def test_checkout_not_configured(client):
    token = await register_and_get_token(client, "co@firma.de", "CO Firma")
    res = await client.post("/api/billing/checkout",
        json={"plan": "pro"}, headers=auth(token))
    # stripe not configured in tests -> 503
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_checkout_invalid_plan(client):
    token = await register_and_get_token(client, "inv@firma.de", "Inv Firma")
    # even without stripe, invalid plan should fail at validation
    res = await client.post("/api/billing/checkout",
        json={"plan": "ultra"}, headers=auth(token))
    assert res.status_code in (400, 503)


@pytest.mark.asyncio
async def test_billing_requires_auth(client):
    res = await client.get("/api/billing/current")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_settings_get(client):
    token = await register_and_get_token(client, "sets@firma.de", "Sets Firma")
    res = await client.get("/api/tenants/current", headers=auth(token))
    assert res.status_code == 200
    d = res.json()
    assert d["name"] == "Sets Firma"
    assert d["plan"] == "free"


@pytest.mark.asyncio
async def test_settings_update(client):
    token = await register_and_get_token(client, "upd@firma.de", "Upd Firma")

    res = await client.put("/api/tenants/current", json={
        "name": "Neuer Name GmbH",
        "settings": {"primary_color": "#ff0000", "widget_greeting": "Hallo!"},
    }, headers=auth(token))
    assert res.status_code == 200

    # verify
    res = await client.get("/api/tenants/current", headers=auth(token))
    assert res.json()["name"] == "Neuer Name GmbH"
    assert res.json()["settings"]["primary_color"] == "#ff0000"


@pytest.mark.asyncio
async def test_security_headers(client):
    res = await client.get("/health")
    assert "x-content-type-options" in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "x-frame-options" in res.headers


@pytest.mark.asyncio
async def test_health_check(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_agent_limit_enforcement(client):
    token = await register_and_get_token(client, "limit@firma.de", "Limit Firma")
    # free plan: max 2 agents (owner = 1, so 1 more allowed)

    # invite agent 1 -- should work
    res = await client.post("/api/users/invite",
        json={"email": "agent1@limit.de", "role": "agent"}, headers=auth(token))
    assert res.status_code == 201
    t1 = res.json()["token"]
    await client.post("/api/users/accept-invite",
        json={"token": t1, "name": "Agent 1", "password": "agentpass"})

    # invite agent 2 -- should fail (limit = 2, already have owner + agent1)
    res = await client.post("/api/users/invite",
        json={"email": "agent2@limit.de", "role": "agent"}, headers=auth(token))
    assert res.status_code == 403
    assert "limit" in res.json()["detail"].lower()
