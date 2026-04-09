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
async def test_portal_info(client):
    await register_and_get_token(client, "info@portal.de", "Portal Firma")
    res = await client.get("/api/portal/portal-firma/info")
    assert res.status_code == 200
    assert res.json()["name"] == "Portal Firma"
    assert res.json()["slug"] == "portal-firma"


@pytest.mark.asyncio
async def test_portal_info_invalid_slug(client):
    res = await client.get("/api/portal/gibts-nicht/info")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_portal_submit_ticket(client):
    await register_and_get_token(client, "submit@portal.de", "Submit Corp")
    res = await client.post("/api/portal/submit-corp/tickets", json={
        "email": "kunde@extern.de",
        "name": "Max Kunde",
        "subject": "Hilfe bitte",
        "body": "Irgendwas geht nicht.",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ticket_number"] == 1
    assert "customer_token" in data


@pytest.mark.asyncio
async def test_portal_list_and_track(client):
    await register_and_get_token(client, "track@portal.de", "Track Corp")

    # submit ticket
    res = await client.post("/api/portal/track-corp/tickets", json={
        "email": "tracker@extern.de",
        "subject": "Problem 1",
        "body": "Details hier.",
    })
    data = res.json()
    token = data["customer_token"]
    ticket_id = data["ticket_id"]

    # list tickets
    res = await client.get(f"/api/portal/track-corp/tickets?token={token}")
    assert res.status_code == 200
    tickets = res.json()
    assert len(tickets) == 1
    assert tickets[0]["subject"] == "Problem 1"

    # get detail
    res = await client.get(f"/api/portal/track-corp/tickets/{ticket_id}?token={token}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["subject"] == "Problem 1"
    assert len(detail["messages"]) == 1


@pytest.mark.asyncio
async def test_portal_customer_reply(client):
    await register_and_get_token(client, "reply@portal.de", "Reply Corp")

    res = await client.post("/api/portal/reply-corp/tickets", json={
        "email": "replier@extern.de",
        "subject": "Reply Test",
        "body": "Erste Nachricht.",
    })
    data = res.json()
    token = data["customer_token"]
    ticket_id = data["ticket_id"]

    # customer replies
    res = await client.post(
        f"/api/portal/reply-corp/tickets/{ticket_id}/reply?token={token}",
        json={"body": "Nachtrag: Hier noch ein Screenshot."},
    )
    assert res.status_code == 200

    # check messages
    res = await client.get(f"/api/portal/reply-corp/tickets/{ticket_id}?token={token}")
    assert len(res.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_portal_invalid_token(client):
    await register_and_get_token(client, "inv@portal.de", "Inv Corp")
    res = await client.get("/api/portal/inv-corp/tickets?token=fake-token")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_portal_internal_notes_hidden(client):
    agent_token = await register_and_get_token(client, "hidden@portal.de", "Hidden Corp")

    # submit via portal
    res = await client.post("/api/portal/hidden-corp/tickets", json={
        "email": "outsider@extern.de",
        "subject": "Hidden Notes Test",
        "body": "Kundennachricht.",
    })
    data = res.json()
    customer_token = data["customer_token"]
    ticket_id = data["ticket_id"]

    # agent adds internal note
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "GEHEIM: Interner Kommentar",
        "is_internal": True,
    }, headers=auth(agent_token))

    # agent adds public reply
    await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "body": "Wir kuemmern uns drum!",
        "is_internal": False,
    }, headers=auth(agent_token))

    # customer should only see 2 messages (initial + public reply), NOT the internal note
    res = await client.get(f"/api/portal/hidden-corp/tickets/{ticket_id}?token={customer_token}")
    messages = res.json()["messages"]
    assert len(messages) == 2
    for m in messages:
        assert "GEHEIM" not in m["body"]


@pytest.mark.asyncio
async def test_portal_reopen_on_customer_reply(client):
    agent_token = await register_and_get_token(client, "reopen@portal.de", "Reopen Corp")

    # submit ticket
    res = await client.post("/api/portal/reopen-corp/tickets", json={
        "email": "reopener@extern.de",
        "subject": "Reopen Test",
        "body": "Problem.",
    })
    data = res.json()
    customer_token = data["customer_token"]
    ticket_id = data["ticket_id"]

    # agent resolves
    await client.put(f"/api/tickets/{ticket_id}", json={"status": "resolved"}, headers=auth(agent_token))

    # customer replies -> should reopen
    await client.post(
        f"/api/portal/reopen-corp/tickets/{ticket_id}/reply?token={customer_token}",
        json={"body": "Problem ist wieder da!"},
    )

    # check status via agent API
    res = await client.get(f"/api/tickets/{ticket_id}", headers=auth(agent_token))
    assert res.json()["status"] == "open"
