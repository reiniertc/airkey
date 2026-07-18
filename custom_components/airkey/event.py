"""Event entity for the EVVA Airkey audit trail."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirkeyConfigEntry
from .const import API_EVENT_TYPE_MAP, EVENT_TYPES
from .coordinator import AirkeyDataUpdateCoordinator
from .entity import AirkeyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirkeyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airkey event entity from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AirkeyAccessEventEntity(coordinator)])


class AirkeyAccessEventEntity(AirkeyEntity, EventEntity):
    """Represents the Airkey access audit trail (unlocking, pairing, sync)."""

    _attr_translation_key = "access_events"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "access_events")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_new_events)
        )

    @callback
    def _handle_new_events(self) -> None:
        if not self.coordinator.data:
            return
        new_events = sorted(
            self.coordinator.data.new_events,
            key=lambda event: event.get("timestamp") or "",
        )
        triggered = False
        for event in new_events:
            details = event.get("details") or {}
            api_type = details.get("type")
            event_type = API_EVENT_TYPE_MAP.get(api_type)
            if event_type is None:
                continue
            attributes = {key: value for key, value in details.items() if key != "type"}
            attributes["airkey_event_id"] = event.get("id")
            attributes["timestamp"] = event.get("timestamp")
            self._trigger_event(event_type, attributes)
            triggered = True
        if triggered:
            self.async_write_ha_state()
