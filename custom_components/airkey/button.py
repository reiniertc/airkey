"""Buttons for the EVVA Airkey integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirkeyConfigEntry
from .const import CONF_ENVIRONMENT, ENV_TEST
from .coordinator import AirkeyDataUpdateCoordinator
from .entity import AirkeyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirkeyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airkey buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[ButtonEntity] = [AirkeyRefreshButton(coordinator)]
    if entry.data.get(CONF_ENVIRONMENT) == ENV_TEST:
        entities.append(AirkeyResetTestDataButton(coordinator))

    async_add_entities(entities)


class AirkeyRefreshButton(AirkeyEntity, ButtonEntity):
    """Button that forces an immediate refresh of all Airkey data."""

    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class AirkeyResetTestDataButton(AirkeyEntity, ButtonEntity):
    """Button that resets the Airkey integration test environment data.

    Only available when the config entry is configured for the free
    integration/test environment - it has no effect on production data.
    """

    _attr_translation_key = "reset_test_data"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "reset_test_data")

    async def async_press(self) -> None:
        await self.coordinator.client.reset_test_data()
        await self.coordinator.async_request_refresh()
