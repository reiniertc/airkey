"""Tests for the Airkey services."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airkey.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_ENVIRONMENT,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    ENV_PRODUCTION,
    ISSUE_WRITE_ACCESS_DENIED,
    SERVICE_CREATE_PERSON,
    SERVICE_REFRESH,
)

from .conftest import API_BASE, register_empty_account


@pytest.fixture
async def loaded_entry(hass, aioclient_mock):
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
    return entry


async def test_all_services_are_registered(hass, loaded_entry) -> None:
    from custom_components.airkey import const as airkey_const

    service_names = {
        getattr(airkey_const, name)
        for name in dir(airkey_const)
        if name.startswith("SERVICE_")
    }
    for service_name in service_names:
        assert hass.services.has_service(DOMAIN, service_name), service_name


async def test_refresh_service(hass, loaded_entry, aioclient_mock) -> None:
    call_count_before = len(aioclient_mock.mock_calls)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH,
        {ATTR_CONFIG_ENTRY_ID: loaded_entry.entry_id},
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) > call_count_before


async def test_create_person_success(hass, loaded_entry, aioclient_mock) -> None:
    aioclient_mock.post(f"{API_BASE}/persons", json=[{"id": 1, "version": 0}])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PERSON,
        {
            ATTR_CONFIG_ENTRY_ID: loaded_entry.entry_id,
            "first_name": "Jane",
            "last_name": "Doe",
            "correspondence_language_code": "en-UK",
        },
        blocking=True,
    )


async def test_create_person_forbidden_raises_and_creates_issue(
    hass, loaded_entry, aioclient_mock
) -> None:
    aioclient_mock.post(f"{API_BASE}/persons", status=403)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_PERSON,
            {
                ATTR_CONFIG_ENTRY_ID: loaded_entry.entry_id,
                "first_name": "Jane",
                "last_name": "Doe",
                "correspondence_language_code": "en-UK",
            },
            blocking=True,
        )

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"{ISSUE_WRITE_ACCESS_DENIED}_{loaded_entry.entry_id}"
    )
    assert issue is not None
