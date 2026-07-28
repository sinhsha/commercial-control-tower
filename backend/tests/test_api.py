"""Integration tests for the health and hotel endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.anyio
async def test_health(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "database" in data


@pytest.mark.anyio
async def test_list_hotels(client: AsyncClient):
    response = await client.get("/api/v1/hotels")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    # Seeder should have populated hotels
    assert data["total"] >= 5


@pytest.mark.anyio
async def test_get_hotel_not_found(client: AsyncClient):
    response = await client.get("/api/v1/hotels/non-existent-id")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_dashboard(client: AsyncClient):
    # First get a hotel ID from the list
    hotels_resp = await client.get("/api/v1/hotels")
    hotels_data = hotels_resp.json()
    assert hotels_data["total"] > 0
    hotel_id = hotels_data["items"][0]["id"]

    response = await client.get(f"/api/v1/metrics/dashboard/{hotel_id}")
    assert response.status_code == 200
    data = response.json()
    assert "occupancy_pct" in data
    assert "adr" in data
    assert "revpar" in data
    assert "available_rooms" in data
    assert "demand_trend" in data
    assert 0.0 <= data["occupancy_pct"] <= 100.0
