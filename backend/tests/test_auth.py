import pytest


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    response = await client.post(
        "/auth/login", data={"username": "operator@test.example.com", "password": "securepass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client, test_user):
    response = await client.post(
        "/auth/login", data={"username": "operator@test.example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_access_protected_route_without_token(client):
    response = await client.get("/leaks/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_protected_route_with_valid_token(client, test_user):
    # Get token
    login_res = await client.post(
        "/auth/login", data={"username": "operator@test.example.com", "password": "securepass123"}
    )
    token = login_res.json()["access_token"]

    # Access leaks
    response = await client.get("/leaks/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
