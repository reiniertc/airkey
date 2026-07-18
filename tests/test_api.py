"""Tests for the Airkey API client."""

from __future__ import annotations

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.airkey.api import (
    AirkeyApiClient,
    AirkeyAuthError,
    AirkeyForbiddenError,
    AirkeyRateLimitError,
)

BASE = "https://api.airkey.evva.com/cloud/v1"


async def test_get_persons_paginates(hass, aioclient_mock) -> None:
    aioclient_mock.get(
        f"{BASE}/persons",
        params={"offset": "0", "limit": "100"},
        json={"offset": 0, "total": 3, "personList": [{"id": 1}, {"id": 2}]},
    )
    aioclient_mock.get(
        f"{BASE}/persons",
        params={"offset": "2", "limit": "100"},
        json={"offset": 2, "total": 3, "personList": [{"id": 3}]},
    )

    client = AirkeyApiClient(async_get_clientsession(hass), "key", "production")
    persons = await client.get_persons()

    assert [p["id"] for p in persons] == [1, 2, 3]


async def test_401_raises_auth_error(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/customer", status=401)
    client = AirkeyApiClient(async_get_clientsession(hass), "bad-key", "production")

    with pytest.raises(AirkeyAuthError):
        await client.get_customer()


async def test_403_raises_forbidden_error(hass, aioclient_mock) -> None:
    aioclient_mock.post(f"{BASE}/persons", status=403)
    client = AirkeyApiClient(
        async_get_clientsession(hass), "readonly-key", "production"
    )

    with pytest.raises(AirkeyForbiddenError):
        await client.create_persons([{"firstName": "A"}])


async def test_429_raises_rate_limit_error_with_retry_after(
    hass, aioclient_mock
) -> None:
    aioclient_mock.get(f"{BASE}/locks", status=429, headers={"Retry-After": "12"})
    client = AirkeyApiClient(async_get_clientsession(hass), "key", "production")

    with pytest.raises(AirkeyRateLimitError) as exc_info:
        await client.get_locks()

    assert exc_info.value.retry_after == 12.0


async def test_blacklists_returns_raw_list(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/blacklists", json=[{"lockId": 1, "mediumId": 2}])
    client = AirkeyApiClient(async_get_clientsession(hass), "key", "production")

    entries = await client.get_blacklists()

    assert entries == [{"lockId": 1, "mediumId": 2}]


async def test_test_environment_uses_integration_host(hass, aioclient_mock) -> None:
    aioclient_mock.get(
        "https://integration.api.airkey.evva.com/cloud/v1/customer",
        json={"customerNumber": "TEST-1"},
    )
    client = AirkeyApiClient(async_get_clientsession(hass), "key", "test")

    customer = await client.get_customer()

    assert customer["customerNumber"] == "TEST-1"
