"""Tests for setting up and unloading the Airkey integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airkey.const import (
    CONF_ENVIRONMENT,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    ENV_PRODUCTION,
)

from .conftest import API_BASE, register_empty_account


async def test_setup_and_unload_entry(hass, aioclient_mock) -> None:
    register_empty_account(aioclient_mock)
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

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.airkey_credits").state == "100"
    assert hass.states.get("sensor.airkey_persons").state == "0"
    assert hass.states.get("button.airkey_refresh_data") is not None
    assert hass.states.get("event.airkey_access_events") is not None
    assert hass.services.has_service(DOMAIN, "refresh")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_entities_stay_available_after_failed_refresh(
    hass, aioclient_mock
) -> None:
    """A single failed refresh (e.g. hitting Airkey's rate limit) must not
    make entities go unavailable - the last known good data should keep
    showing until a refresh actually succeeds again."""
    register_empty_account(aioclient_mock)
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
    assert hass.states.get("sensor.airkey_credits").state == "100"

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE}/customer", status=429)

    await entry.runtime_data.coordinator.async_refresh()

    assert entry.runtime_data.coordinator.last_update_success is False
    credits_state = hass.states.get("sensor.airkey_credits")
    assert credits_state.state == "100"


async def test_lock_sensor_resolves_last_used_person(hass, aioclient_mock) -> None:
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
        f"{API_BASE}/lock-protocol-limit",
        params={"lockId": "1"},
        json={
            "offset": 0,
            "total": 1,
            "lockProtocols": [
                {
                    "event": {"type": "UNLOCKING_SUCCESSFUL"},
                    "medium": {"id": 5, "name": "Jane's card"},
                    "timestamp": "2026-07-01T10:00:00.000Z",
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

    state = hass.states.get("sensor.airkey_front_door_lock")
    assert state is not None
    assert state.attributes["last_used_by_medium_name"] == "Jane's card"
    assert state.attributes["last_used_by_person_id"] == 10
    assert state.attributes["last_used_by_person_name"] == "Jane Doe"


async def test_migration_from_v1(hass, aioclient_mock) -> None:
    register_empty_account(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_SCAN_INTERVAL: 20},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == CONFIG_ENTRY_VERSION
    assert entry.data[CONF_ENVIRONMENT] == ENV_PRODUCTION
    assert CONF_SCAN_INTERVAL not in entry.data
    assert entry.options[CONF_SCAN_INTERVAL] == 20
    assert entry.unique_id == "production:CUST-1"
    assert entry.state is ConfigEntryState.LOADED
