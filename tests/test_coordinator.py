"""Tests for the Airkey data update coordinator."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.airkey.api import AirkeyApiClient
from custom_components.airkey.const import CONF_ENVIRONMENT, DOMAIN, ENV_PRODUCTION
from custom_components.airkey.coordinator import AirkeyDataUpdateCoordinator

from .conftest import API_BASE, register_empty_account


async def _make_coordinator(hass, aioclient_mock, locks=None, assigned_areas=None):
    register_empty_account(aioclient_mock, locks=locks, assigned_areas=assigned_areas)
    entry = await _create_entry(hass)
    client = AirkeyApiClient(async_get_clientsession(hass), "key", ENV_PRODUCTION)
    return AirkeyDataUpdateCoordinator(hass, entry, client)


async def _create_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_ENVIRONMENT: ENV_PRODUCTION},
        options={"scan_interval": 15, "event_lookback_hours": 24},
        unique_id="production:CUST-1",
    )
    entry.add_to_hass(hass)
    return entry


async def test_first_refresh_populates_data(hass, aioclient_mock) -> None:
    coordinator = await _make_coordinator(hass, aioclient_mock)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.customer["customerNumber"] == "CUST-1"
    assert coordinator.data.credits["quantityCreditsAmount"] == 100
    assert coordinator.data.locks == []


async def test_second_refresh_uses_last_poll_as_created_after(
    hass, aioclient_mock
) -> None:
    coordinator = await _make_coordinator(hass, aioclient_mock)
    await coordinator.async_refresh()
    assert coordinator._last_event_poll is not None
    first_poll = coordinator._last_event_poll

    await coordinator.async_refresh()

    events_calls = [
        call for call in aioclient_mock.mock_calls if call[1].path.endswith("/events")
    ]
    assert len(events_calls) == 2
    assert events_calls[0][1].query.get("createdAfter") != first_poll
    assert events_calls[1][1].query.get("createdAfter") == first_poll


async def test_lock_last_used_from_protocol(hass, aioclient_mock) -> None:
    lock = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    aioclient_mock.get(
        f"{API_BASE}/lock-protocol-limit",
        params={"lockId": "1"},
        json={
            "offset": 0,
            "total": 2,
            "lockProtocols": [
                {
                    "event": {"type": "UNLOCKING_SUCCESSFUL"},
                    "medium": {"id": 42, "name": "Jane's card"},
                    "timestamp": "2026-07-01T10:00:00.000Z",
                },
                {
                    "event": {"type": "CYLINDER_SYNCHRONIZATION_VIA_OTA"},
                    "medium": {"id": 99, "name": "Sync medium"},
                    "timestamp": "2026-07-10T10:00:00.000Z",
                },
                {
                    "event": {"type": "UNLOCKING_SUCCESSFUL"},
                    "medium": {"id": 7, "name": "John's phone"},
                    "timestamp": "2026-07-05T08:30:00.000Z",
                },
            ],
        },
    )
    coordinator = await _make_coordinator(hass, aioclient_mock, locks=[lock])

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    # Most recent *successful unlock* wins - the later sync event is ignored.
    usage = coordinator.data.lock_last_used[1]
    assert usage["timestamp"] == "2026-07-05T08:30:00.000Z"
    assert usage["medium_id"] == 7
    assert usage["medium_name"] == "John's phone"

    medium_usage = coordinator.data.medium_last_used[7]
    assert medium_usage["lock_id"] == 1
    assert medium_usage["lock_name"] == "Front door"


async def test_area_locks_index_built_from_per_lock_assignments(
    hass, aioclient_mock
) -> None:
    front_door = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    back_door = {"id": 2, "lockDoor": {"name": "Back door"}, "version": 1}
    coordinator = await _make_coordinator(
        hass,
        aioclient_mock,
        locks=[front_door, back_door],
        assigned_areas={
            1: [{"id": 100, "name": "Garden"}],
            2: [{"id": 100, "name": "Garden"}, {"id": 200, "name": "House"}],
        },
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    garden_locks = {lock["id"] for lock in coordinator.data.area_locks[100]}
    assert garden_locks == {1, 2}
    house_locks = {lock["id"] for lock in coordinator.data.area_locks[200]}
    assert house_locks == {2}


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_lock_details_only_refreshed_once_per_interval(
    hass, aioclient_mock
) -> None:
    """async_refresh_lock_details() goes through the coordinator's debounced
    async_request_refresh(), which schedules a cooldown-reset timer that
    outlives this test - expected_lingering_timers acknowledges that."""
    lock = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    coordinator = await _make_coordinator(hass, aioclient_mock, locks=[lock])

    def _protocol_call_count() -> int:
        return len(
            [
                c
                for c in aioclient_mock.mock_calls
                if c[1].path.endswith("/lock-protocol-limit")
            ]
        )

    await coordinator.async_refresh()
    assert _protocol_call_count() == 1

    # A second refresh well within the default 24h interval must not
    # re-fetch the per-lock usage/area data.
    await coordinator.async_refresh()
    assert _protocol_call_count() == 1
    assert coordinator.data.lock_last_used == {}

    # But the manual "refresh lock details" service/method forces it.
    await coordinator.async_refresh_lock_details()
    assert _protocol_call_count() == 2
