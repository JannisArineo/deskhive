import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post("/api/auth/register", json={
        "email": "owner@testfirma.de",
        "password": "sicherespasswort",
        "name": "Test Owner",
        "company_name": "Test Firma",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dupe@testfirma.de",
        "password": "sicherespasswort",
        "name": "Test Owner",
        "company_name": "Dupe Firma",
    }
    res1 = await client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # same email in different tenant should still work (different company)
    payload2 = {**payload, "company_name": "Andere Firma"}
    res2 = await client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 201


@pytest.mark.asyncio
async def test_login_success(client):
    # register first
    await client.post("/api/auth/register", json={
        "email": "login@test.de",
        "password": "testpasswort123",
        "name": "Login User",
        "company_name": "Login Corp",
    })

    # login
    res = await client.post("/api/auth/login", json={
        "email": "login@test.de",
        "password": "testpasswort123",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "wrong@test.de",
        "password": "richtigespasswort",
        "name": "Wrong User",
        "company_name": "Wrong Corp",
    })

    res = await client.post("/api/auth/login", json={
        "email": "wrong@test.de",
        "password": "falschespasswort",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    res = await client.post("/api/auth/login", json={
        "email": "gibts@nicht.de",
        "password": "egal",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client):
    # register to get refresh token cookie
    res = await client.post("/api/auth/register", json={
        "email": "refresh@test.de",
        "password": "testpasswort",
        "name": "Refresh User",
        "company_name": "Refresh Corp",
    })
    assert res.status_code == 201

    # refresh
    refresh_res = await client.post("/api/auth/refresh")
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_logout(client):
    await client.post("/api/auth/register", json={
        "email": "logout@test.de",
        "password": "testpasswort",
        "name": "Logout User",
        "company_name": "Logout Corp",
    })

    res = await client.post("/api/auth/logout")
    assert res.status_code == 200

    # refresh should fail after logout
    refresh_res = await client.post("/api/auth/refresh")
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
