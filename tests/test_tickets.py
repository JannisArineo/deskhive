import pytest


async def register_and_get_token(client, email, company):
    res = await client.post("/api/auth/register", json={
        "email": email, "password": "testpasswort123",
        "name": "Test User", "company_name": company,
    })
    return res.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_ticket(client):
    token = await register_and_get_token(client, "agent@firma.de", "Ticket Firma")

    res = await client.post("/api/tickets", json={
        "subject": "Login geht nicht",
        "body": "Ich kann mich nicht einloggen seit heute morgen.",
        "priority": "high",
        "customer_email": "kunde@extern.de",
        "customer_name": "Max Kunde",
    }, headers=auth(token))

    assert res.status_code == 201
    data = res.json()
    assert data["ticket_number"] == 1
    assert data["subject"] == "Login geht nicht"
    assert data["status"] == "open"
    assert data["priority"] == "high"
    assert data["customer_email"] == "kunde@extern.de"


@pytest.mark.asyncio
async def test_list_tickets(client):
    token = await register_and_get_token(client, "list@firma.de", "List Firma")

    # create 3 tickets
    for i in range(3):
        await client.post("/api/tickets", json={
            "subject": f"Ticket {i+1}",
            "body": f"Body {i+1}",
            "customer_email": f"kunde{i}@test.de",
        }, headers=auth(token))

    res = await client.get("/api/tickets", headers=auth(token))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["tickets"]) == 3


@pytest.mark.asyncio
async def test_filter_by_status(client):
    token = await register_and_get_token(client, "filter@firma.de", "Filter Firma")

    # create ticket
    res = await client.post("/api/tickets", json={
        "subject": "Offen", "body": "test", "customer_email": "k@t.de",
    }, headers=auth(token))
    ticket_id = res.json()["id"]

    # mark as resolved
    await client.put(f"/api/tickets/{ticket_id}", json={"status": "resolved"}, headers=auth(token))

    # filter open -- should be 0
    res = await client.get("/api/tickets?status=open", headers=auth(token))
    assert res.json()["total"] == 0

    # filter resolved -- should be 1
    res = await client.get("/api/tickets?status=resolved", headers=auth(token))
    assert res.json()["total"] == 1


@pytest.mark.asyncio
async def test_ticket_detail_with_messages(client):
    token = await register_and_get_token(client, "detail@firma.de", "Detail Firma")

    # create ticket (has 1 initial message)
    res = await client.post("/api/tickets", json={
        "subject": "Detail Test", "body": "Initial message",
        "customer_email": "d@t.de",
    }, headers=auth(token))
    ticket_id = res.json()["id"]

    # add reply
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "Wir schauen uns das an.", "is_internal": False,
    }, headers=auth(token))

    # add internal note
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "Sieht nach DB-Problem aus.", "is_internal": True,
    }, headers=auth(token))

    # get detail
    res = await client.get(f"/api/tickets/{ticket_id}", headers=auth(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data["messages"]) == 3
    assert data["messages"][0]["body"] == "Initial message"
    assert data["messages"][1]["is_internal"] == False
    assert data["messages"][2]["is_internal"] == True


@pytest.mark.asyncio
async def test_auto_status_change_on_reply(client):
    token = await register_and_get_token(client, "auto@firma.de", "Auto Firma")

    res = await client.post("/api/tickets", json={
        "subject": "Auto Test", "body": "test",
        "customer_email": "a@t.de",
    }, headers=auth(token))
    ticket_id = res.json()["id"]
    assert res.json()["status"] == "open"

    # reply -> should auto-set to in_progress
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "Antwort", "is_internal": False,
    }, headers=auth(token))

    res = await client.get(f"/api/tickets/{ticket_id}", headers=auth(token))
    assert res.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_internal_note_no_status_change(client):
    token = await register_and_get_token(client, "internal@firma.de", "Internal Firma")

    res = await client.post("/api/tickets", json={
        "subject": "Internal Test", "body": "test",
        "customer_email": "i@t.de",
    }, headers=auth(token))
    ticket_id = res.json()["id"]

    # internal note should NOT change status
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "Notiz", "is_internal": True,
    }, headers=auth(token))

    res = await client.get(f"/api/tickets/{ticket_id}", headers=auth(token))
    assert res.json()["status"] == "open"


@pytest.mark.asyncio
async def test_ticket_number_auto_increment(client):
    token = await register_and_get_token(client, "num@firma.de", "Num Firma")

    for i in range(3):
        res = await client.post("/api/tickets", json={
            "subject": f"Ticket {i}", "body": "test",
            "customer_email": f"n{i}@t.de",
        }, headers=auth(token))
        assert res.json()["ticket_number"] == i + 1


@pytest.mark.asyncio
async def test_tenant_isolation():
    """User from tenant A cannot see tenant B's tickets."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        token_a = await register_and_get_token(client_a, "a@firma-a.de", "Firma A")

        # create ticket in tenant A
        res = await client_a.post("/api/tickets", json={
            "subject": "Geheim A", "body": "Nur fuer Firma A",
            "customer_email": "kunde@a.de",
        }, headers=auth(token_a))
        ticket_a_id = res.json()["id"]

    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        token_b = await register_and_get_token(client_b, "b@firma-b.de", "Firma B")

        # tenant B should see 0 tickets
        res = await client_b.get("/api/tickets", headers=auth(token_b))
        assert res.json()["total"] == 0

        # tenant B should get 404 for tenant A's ticket
        res = await client_b.get(f"/api/tickets/{ticket_a_id}", headers=auth(token_b))
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_ticket(client):
    token = await register_and_get_token(client, "update@firma.de", "Update Firma")

    res = await client.post("/api/tickets", json={
        "subject": "Update Test", "body": "test",
        "customer_email": "u@t.de",
    }, headers=auth(token))
    ticket_id = res.json()["id"]

    # update priority
    res = await client.put(f"/api/tickets/{ticket_id}", json={"priority": "urgent"}, headers=auth(token))
    assert res.status_code == 200
    assert res.json()["priority"] == "urgent"

    # resolve -> resolved_at should be set
    res = await client.put(f"/api/tickets/{ticket_id}", json={"status": "resolved"}, headers=auth(token))
    assert res.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_search_tickets(client):
    token = await register_and_get_token(client, "search@firma.de", "Search Firma")

    await client.post("/api/tickets", json={
        "subject": "Login Problem", "body": "test", "customer_email": "s1@t.de",
    }, headers=auth(token))
    await client.post("/api/tickets", json={
        "subject": "Passwort vergessen", "body": "test", "customer_email": "s2@t.de",
    }, headers=auth(token))

    res = await client.get("/api/tickets?search=Login", headers=auth(token))
    assert res.json()["total"] == 1
    assert "Login" in res.json()["tickets"][0]["subject"]
