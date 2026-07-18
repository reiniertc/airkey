"""The EVVA Airkey integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirkeyApiClient, AirkeyAuthError, AirkeyError
from .const import (
    CONF_ENVIRONMENT,
    CONF_EVENT_LOOKBACK_HOURS,
    DEFAULT_EVENT_LOOKBACK_HOURS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    ENV_PRODUCTION,
)
from .coordinator import AirkeyDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
]


@dataclass
class AirkeyRuntimeData:
    """Data stored on the config entry while it is set up."""

    client: AirkeyApiClient
    coordinator: AirkeyDataUpdateCoordinator


type AirkeyConfigEntry = ConfigEntry[AirkeyRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Airkey integration (register the shared services once)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AirkeyConfigEntry) -> bool:
    """Set up Airkey from a config entry."""
    session = async_get_clientsession(hass)
    client = AirkeyApiClient(
        session, entry.data[CONF_API_KEY], entry.data[CONF_ENVIRONMENT]
    )
    coordinator = AirkeyDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AirkeyRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: AirkeyConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AirkeyConfigEntry) -> bool:
    """Unload an Airkey config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current version."""
    if entry.version == 1:
        _LOGGER.debug("Migrating Airkey config entry from version 1 to 2")
        data = {**entry.data}
        api_key = data.get(CONF_API_KEY)
        environment = data.setdefault(CONF_ENVIRONMENT, ENV_PRODUCTION)

        options = {
            CONF_SCAN_INTERVAL: data.pop(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
            ),
            CONF_EVENT_LOOKBACK_HOURS: DEFAULT_EVENT_LOOKBACK_HOURS,
        }

        unique_id = entry.unique_id
        if unique_id is None and api_key:
            session = async_get_clientsession(hass)
            client = AirkeyApiClient(session, api_key, environment)
            try:
                customer = await client.get_customer()
            except (AirkeyAuthError, AirkeyError):
                customer = None
            if customer and customer.get("customerNumber"):
                unique_id = f"{environment}:{customer['customerNumber']}"

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            unique_id=unique_id,
            version=2,
        )

    return True
