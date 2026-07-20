"""Tests for the Airkey access-events entity."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airkey.const import (
    CONF_ENVIRONMENT,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    ENV_PRODUCTION,
)

from .conftest import API_BASE, register_empty_account


async def test_unlocking_event_resolves_lock_medium_and_person(
    hass, aioclient_mock
) -> None:
    lock = {"id": 1, "lockDoor": {"name": "Front door"}, "version": 1}

    aioclient_mock.get(
        f"{API_BASE}/persons",
        json={
            "offset": 0,
            "total": 1,
            "personList": [{"id": 10, "firstName": "Jane", "lastName": "Doe"}],
        },
    )
    aioclient_mock.get(
        f"{API_BASE}/media/cards",
        json={
            "offset": 0,
            "total": 1,
            "mediumList": [{"id": 5, "name": "Jane's card", "personId": 10}],
        },
    )
    aioclient_mock.get(
        f"{API_BASE}/events",
        json={
            "offset": 0,
            "total": 1,
            "events": [
                {
                    "id": 99,
                    "timestamp": "2026-07-01T10:00:00.000Z",
                    "details": {
                        "type": "UNLOCKING",
                        "lockId": 1,
                        "mediumId": 5,
                        "unlockingTimestamp": "2026-07-01T09:59:58.000Z",
                    },
                }
            ],
        },
    )

    register_empty_account(aioclient_mock, locks=[lock])
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_ENVIRONMENT: ENV_PRODUCTION},
        options={CONF_SCAN_INTERVAL: 15, "event_lookback_hours": 24},
        unique_id="production:CUST-1",
        version=CONFIG_ENTRY_VERSION,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("event.airkey_access_events")
    assert state is not None
    assert state.attributes["event_type"] == "unlocking"
    assert state.attributes["lock_id"] == 1
    assert state.attributes["lock_name"] == "Front door"
    assert state.attributes["medium_id"] == 5
    assert state.attributes["medium_name"] == "Jane's card"
    assert state.attributes["person_id"] == 10
    assert state.attributes["person_name"] == "Jane Doe"
