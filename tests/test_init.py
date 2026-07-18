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

from .conftest import register_empty_account


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
