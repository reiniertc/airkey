"""Event entity for the EVVA Airkey audit trail."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirkeyConfigEntry
from .const import API_EVENT_TYPE_MAP, EVENT_TYPES
from .coordinator import AirkeyData, AirkeyDataUpdateCoordinator
from .entity import AirkeyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirkeyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airkey event entity from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AirkeyAccessEventEntity(coordinator)])


def _lock_names_by_id(data: AirkeyData) -> dict[int, str]:
    names: dict[int, str] = {}
    for lock in data.locks:
        door = lock.get("lockDoor") or {}
        lock_id = lock.get("id")
        names[lock_id] = (
            door.get("name") or door.get("alternativeName") or f"Lock {lock_id}"
        )
    return names


def _media_by_id(data: AirkeyData) -> dict[int, dict]:
    return {m.get("id"): m for m in [*data.cards, *data.phones]}


def _person_names_by_id(data: AirkeyData) -> dict[int, str]:
    return {
        p.get("id"): f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
        for p in data.persons
    }


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
        # The coordinator's first refresh (which may already carry recent
        # events, e.g. from the event lookback window) happens before
        # platforms are set up, i.e. before this listener was registered -
        # process whatever it already fetched so those aren't missed.
        self._handle_new_events()

    @callback
    def _handle_new_events(self) -> None:
        data = self.coordinator.data
        if not data:
            return
        new_events = sorted(
            data.new_events, key=lambda event: event.get("timestamp") or ""
        )
        triggered = False
        lock_names = _lock_names_by_id(data)
        media = _media_by_id(data)
        person_names = _person_names_by_id(data)
        for event in new_events:
            details = event.get("details") or {}
            api_type = details.get("type")
            event_type = API_EVENT_TYPE_MAP.get(api_type)
            if event_type is None:
                continue

            lock_id = details.get("lockId")
            medium_id = details.get("mediumId")
            medium = media.get(medium_id) or {}
            person_id = medium.get("personId")

            attributes = {
                "airkey_event_id": event.get("id"),
                "timestamp": event.get("timestamp"),
                "unlocking_timestamp": details.get("unlockingTimestamp"),
                "lock_id": lock_id,
                "lock_name": lock_names.get(lock_id),
                "medium_id": medium_id,
                "medium_name": medium.get("name") or medium.get("mediumIdentifier"),
                "person_id": person_id,
                "person_name": person_names.get(person_id),
            }
            self._trigger_event(event_type, attributes)
            triggered = True
        if triggered:
            self.async_write_ha_state()
