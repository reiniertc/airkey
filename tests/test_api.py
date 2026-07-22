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


async def test_request_count_increments_per_call(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/customer", json={"customerNumber": "1"})
    client = AirkeyApiClient(async_get_clientsession(hass), "key", "production")

    assert client.request_count_today == 0

    await client.get_customer()
    await client.get_customer()

    assert client.request_count_today == 2
    assert client.request_count_date == client._today()


async def test_request_count_counts_failed_requests_too(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/customer", status=401)
    client = AirkeyApiClient(async_get_clientsession(hass), "bad-key", "production")

    with pytest.raises(AirkeyAuthError):
        await client.get_customer()

    assert client.request_count_today == 1


async def test_request_count_resets_on_new_day(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/customer", json={"customerNumber": "1"})
    client = AirkeyApiClient(async_get_clientsession(hass), "key", "production")

    await client.get_customer()
    assert client.request_count_today == 1

    # Simulate the UTC date rolling over without a restart.
    client._request_count_date = "2000-01-01"

    assert client.request_count_today == 0

    await client.get_customer()
    assert client.request_count_today == 1
    assert client.request_count_date != "2000-01-01"


def test_seed_request_count_restores_todays_count() -> None:
    client = AirkeyApiClient(None, "key", "production")

    client.seed_request_count(42, client._today())

    assert client.request_count_today == 42


def test_seed_request_count_ignores_stale_date() -> None:
    client = AirkeyApiClient(None, "key", "production")

    client.seed_request_count(42, "2000-01-01")

    assert client.request_count_today == 0
