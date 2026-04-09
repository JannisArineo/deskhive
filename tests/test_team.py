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
async def test_list_team(client):
    token = await register_and_get_token(client, "team@firma.de", "Team Firma")
    res = await client.get("/api/users", headers=auth(token))
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 1
    assert users[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_get_me(client):
    token = await register_and_get_token(client, "me@firma.de", "Me Firma")
    res = await client.get("/api/users/me", headers=auth(token))
    assert res.status_code == 200
    assert res.json()["email"] == "me@firma.de"
    assert res.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_invite_and_accept(client):
    token = await register_and_get_token(client, "boss@firma.de", "Invite Firma")

    # invite
    res = await client.post("/api/users/invite", json={
        "email": "newagent@firma.de", "role": "agent",
    }, headers=auth(token))
    assert res.status_code == 201
    invite_token = res.json()["token"]

    # accept invite
    res = await client.post("/api/users/accept-invite", json={
        "token": invite_token,
        "name": "New Agent",
        "password": "agentpasswort",
    })
    assert res.status_code == 201

    # new user can login
    res = await client.post("/api/auth/login", json={
        "email": "newagent@firma.de",
        "password": "agentpasswort",
    })
    assert res.status_code == 200
    agent_token = res.json()["access_token"]

    # agent is in same team
    res = await client.get("/api/users", headers=auth(agent_token))
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_invite_invalid_role(client):
    token = await register_and_get_token(client, "role@firma.de", "Role Firma")
    res = await client.post("/api/users/invite", json={
        "email": "hacker@bad.de", "role": "owner",
    }, headers=auth(token))
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_duplicate(client):
    token = await register_and_get_token(client, "dupe@firma.de", "Dupe Firma")
    res = await client.post("/api/users/invite", json={
        "email": "dupe@firma.de", "role": "agent",
    }, headers=auth(token))
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_deactivate_user(client):
    token = await register_and_get_token(client, "deact@firma.de", "Deact Firma")

    # invite + accept
    res = await client.post("/api/users/invite", json={
        "email": "victim@firma.de", "role": "agent",
    }, headers=auth(token))
    invite_token = res.json()["token"]
    await client.post("/api/users/accept-invite", json={
        "token": invite_token, "name": "Victim", "password": "victimpass",
    })

    # get user id
    res = await client.get("/api/users", headers=auth(token))
    victim = [u for u in res.json() if u["email"] == "victim@firma.de"][0]

    # deactivate
    res = await client.delete(f"/api/users/{victim['id']}", headers=auth(token))
    assert res.status_code == 200

    # deactivated user can't login
    res = await client.post("/api/auth/login", json={
        "email": "victim@firma.de", "password": "victimpass",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_cannot_deactivate_self(client):
    token = await register_and_get_token(client, "self@firma.de", "Self Firma")
    res = await client.get("/api/users/me", headers=auth(token))
    my_id = res.json()["id"]

    res = await client.delete(f"/api/users/{my_id}", headers=auth(token))
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_agent_cannot_invite(client):
    token = await register_and_get_token(client, "perm@firma.de", "Perm Firma")

    # invite + accept agent
    res = await client.post("/api/users/invite", json={
        "email": "agent@perm.de", "role": "agent",
    }, headers=auth(token))
    invite_token = res.json()["token"]
    await client.post("/api/users/accept-invite", json={
        "token": invite_token, "name": "Agent", "password": "agentpass",
    })

    # login as agent
    res = await client.post("/api/auth/login", json={
        "email": "agent@perm.de", "password": "agentpass",
    })
    agent_token = res.json()["access_token"]

    # agent tries to invite -> 403
    res = await client.post("/api/users/invite", json={
        "email": "another@perm.de", "role": "agent",
    }, headers=auth(agent_token))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_expired_invite(client):
    token = await register_and_get_token(client, "exp@firma.de", "Exp Firma")

    res = await client.post("/api/users/invite", json={
        "email": "expired@firma.de", "role": "agent",
    }, headers=auth(token))
    invite_token = res.json()["token"]

    # manually expire the invitation
    from sqlalchemy import update
    from app.models.user import Invitation
    from datetime import datetime, timedelta
    from tests.conftest import test_session

    async with test_session() as db:
        await db.execute(
            update(Invitation)
            .where(Invitation.token == invite_token)
            .values(expires_at=datetime.utcnow() - timedelta(days=1))
        )
        await db.commit()

    # try to accept -> should fail
    res = await client.post("/api/users/accept-invite", json={
        "token": invite_token, "name": "Expired", "password": "expiredpass",
    })
    assert res.status_code == 400
