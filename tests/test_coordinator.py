"""Tests for the Airkey data update coordinator."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.airkey.api import AirkeyApiClient
from custom_components.airkey.const import CONF_ENVIRONMENT, DOMAIN, ENV_PRODUCTION
from custom_components.airkey.coordinator import AirkeyDataUpdateCoordinator

from .conftest import register_empty_account


async def _make_coordinator(hass, aioclient_mock):
    register_empty_account(aioclient_mock)
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
