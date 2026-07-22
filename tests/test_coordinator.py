"""Tests for the Airkey data update coordinator."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.airkey.api import AirkeyApiClient
from custom_components.airkey.const import (
    CONF_ENVIRONMENT,
    DOMAIN,
    ENV_PRODUCTION,
    ISSUE_LOCK_DETAILS_ACCESS_DENIED,
)
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


async def test_data_includes_request_count_and_refresh_timestamps(
    hass, aioclient_mock
) -> None:
    coordinator = await _make_coordinator(hass, aioclient_mock)

    await coordinator.async_refresh()

    assert coordinator.data.request_count_today > 0
    assert coordinator.data.request_count_limit == 250
    assert coordinator.data.main_data_last_refreshed is not None
    assert coordinator.data.lock_details_last_refreshed is not None


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

    # Medium 42 unlocked this same lock earlier and isn't the lock's most
    # recent unlocker anymore, but it must still keep its own last-used entry
    # rather than disappearing from medium_last_used entirely.
    other_medium_usage = coordinator.data.medium_last_used[42]
    assert other_medium_usage["timestamp"] == "2026-07-01T10:00:00.000Z"
    assert other_medium_usage["lock_id"] == 1
    assert other_medium_usage["lock_name"] == "Front door"


async def test_medium_last_used_tracks_most_recent_lock_across_multiple_locks(
    hass, aioclient_mock
) -> None:
    """A medium that unlocks two different locks must report the most recent
    of the two, not whichever lock happens to be processed last."""
    front_door = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    back_door = {"id": 2, "lockDoor": {"name": "Back door"}, "version": 1}
    aioclient_mock.get(
        f"{API_BASE}/lock-protocol-limit",
        params={"lockId": "1"},
        json={
            "offset": 0,
            "total": 1,
            "lockProtocols": [
                {
                    "event": {"type": "UNLOCKING_SUCCESSFUL"},
                    "medium": {"id": 7, "name": "John's phone"},
                    "timestamp": "2026-07-01T08:00:00.000Z",
                }
            ],
        },
    )
    aioclient_mock.get(
        f"{API_BASE}/lock-protocol-limit",
        params={"lockId": "2"},
        json={
            "offset": 0,
            "total": 1,
            "lockProtocols": [
                {
                    "event": {"type": "UNLOCKING_SUCCESSFUL"},
                    "medium": {"id": 7, "name": "John's phone"},
                    "timestamp": "2026-07-05T09:00:00.000Z",
                }
            ],
        },
    )
    coordinator = await _make_coordinator(
        hass, aioclient_mock, locks=[front_door, back_door]
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    medium_usage = coordinator.data.medium_last_used[7]
    assert medium_usage["timestamp"] == "2026-07-05T09:00:00.000Z"
    assert medium_usage["lock_id"] == 2
    assert medium_usage["lock_name"] == "Back door"


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


async def test_lock_details_poll_survives_coordinator_recreation(
    hass, aioclient_mock
) -> None:
    """A Home Assistant restart recreates the coordinator from scratch; the
    once-a-day gate must not reset just because of that."""
    lock = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    register_empty_account(aioclient_mock, locks=[lock])
    entry = await _create_entry(hass)
    client = AirkeyApiClient(async_get_clientsession(hass), "key", ENV_PRODUCTION)

    def _protocol_call_count() -> int:
        return len(
            [
                c
                for c in aioclient_mock.mock_calls
                if c[1].path.endswith("/lock-protocol-limit")
            ]
        )

    first_coordinator = AirkeyDataUpdateCoordinator(hass, entry, client)
    await first_coordinator.async_refresh()
    assert _protocol_call_count() == 1

    # Simulate a restart: a brand-new coordinator instance for the same entry.
    second_coordinator = AirkeyDataUpdateCoordinator(hass, entry, client)
    await second_coordinator.async_refresh()

    assert _protocol_call_count() == 1
    assert second_coordinator._last_lock_details_poll is not None


async def test_request_count_persists_across_coordinator_recreation(
    hass, aioclient_mock
) -> None:
    """A Home Assistant restart creates a brand-new API client (whose own
    counter starts at 0) and a brand-new coordinator; the coordinator must
    reseed the new client's counter from the persisted state so the daily
    count doesn't appear to reset just because HA restarted."""
    register_empty_account(aioclient_mock)
    entry = await _create_entry(hass)

    first_client = AirkeyApiClient(async_get_clientsession(hass), "key", ENV_PRODUCTION)
    first_coordinator = AirkeyDataUpdateCoordinator(hass, entry, first_client)
    await first_coordinator.async_refresh()
    count_after_first = first_client.request_count_today
    assert count_after_first > 0

    # Simulate a restart: fresh client (its own counter starts at 0).
    second_client = AirkeyApiClient(
        async_get_clientsession(hass), "key", ENV_PRODUCTION
    )
    assert second_client.request_count_today == 0

    second_coordinator = AirkeyDataUpdateCoordinator(hass, entry, second_client)
    await second_coordinator.async_refresh()

    # The persisted count from before the "restart" plus this cycle's own
    # requests, not just this cycle's requests in isolation.
    assert second_client.request_count_today == 2 * count_after_first
    assert second_coordinator.data.request_count_today == 2 * count_after_first


async def test_forbidden_lock_protocol_creates_repair_issue(
    hass, aioclient_mock
) -> None:
    """A 403 on a *read* endpoint means the account's plan doesn't include
    it - surface a repair issue instead of just failing silently."""
    lock = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}
    aioclient_mock.get(
        f"{API_BASE}/lock-protocol-limit", params={"lockId": "1"}, status=403
    )
    coordinator = await _make_coordinator(hass, aioclient_mock, locks=[lock])

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.lock_last_used == {}
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"{ISSUE_LOCK_DETAILS_ACCESS_DENIED}_{coordinator.entry.entry_id}"
    )
    assert issue is not None
