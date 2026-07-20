"""Sensors for the EVVA Airkey integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import AirkeyConfigEntry
from .coordinator import AirkeyData, AirkeyDataUpdateCoordinator
from .entity import AirkeyEntity, AirkeyLockEntity

_LOGGER = logging.getLogger(__name__)


def _person_name(person: dict) -> str:
    return f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()


def _person_names_by_id(persons: list[dict]) -> dict[int, str]:
    return {p.get("id"): _person_name(p) for p in persons}


def _expand_authorizations(d: AirkeyData) -> list[dict]:
    """Flatten authorizations to one row per (person, lock, medium).

    Area-level authorizations (no specific lock) are expanded into one row
    per lock known to be assigned to that area, using AirkeyData.area_locks,
    so consumers don't need to separately resolve "access to area X" into
    the individual locks that live in it.
    """
    person_names = _person_names_by_id(d.persons)
    rows: list[dict] = []
    for a in d.authorizations:
        base = {
            "id": a.get("id"),
            "person_id": a.get("personId"),
            "person_name": person_names.get(a.get("personId")),
            "medium_id": (a.get("medium") or {}).get("id"),
            "medium_name": (a.get("medium") or {}).get("name")
            or (a.get("medium") or {}).get("mediumIdentifier"),
            "state": a.get("currentState"),
        }
        lock = a.get("lock") or {}
        area = a.get("area") or {}
        area_id = area.get("id")

        if lock.get("id") is not None:
            rows.append(
                {
                    **base,
                    "lock_id": lock.get("id"),
                    "lock_name": lock.get("name"),
                    "area_id": area_id,
                    "area_name": area.get("name"),
                }
            )
        elif area_id is not None and d.area_locks.get(area_id):
            for area_lock in d.area_locks[area_id]:
                rows.append(
                    {
                        **base,
                        "lock_id": area_lock["id"],
                        "lock_name": area_lock["name"],
                        "area_id": area_id,
                        "area_name": area.get("name"),
                    }
                )
        else:
            # Neither a specific lock nor a resolvable area (e.g. an area with
            # no locks known yet) - keep as-is so the record isn't lost.
            rows.append(
                {
                    **base,
                    "lock_id": None,
                    "lock_name": None,
                    "area_id": area_id,
                    "area_name": area.get("name"),
                }
            )
    return rows


@dataclass(frozen=True, kw_only=True)
class AirkeySensorEntityDescription(SensorEntityDescription):
    """Describes an Airkey hub-level sensor."""

    value_fn: Callable[[AirkeyData], StateType]
    attrs_fn: Callable[[AirkeyData], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[AirkeySensorEntityDescription, ...] = (
    AirkeySensorEntityDescription(
        key="credits",
        translation_key="credits",
        native_unit_of_measurement="credits",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.credits.get("quantityCreditsAmount"),
        attrs_fn=lambda d: {
            "valid_until": d.credits.get("temporalCreditEndOfValidity"),
        },
    ),
    AirkeySensorEntityDescription(
        key="persons",
        translation_key="persons",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.persons),
        attrs_fn=lambda d: {
            "persons": [
                {
                    "id": p.get("id"),
                    "name": _person_name(p),
                    "email": p.get("emailAddress"),
                    "phone": p.get("phone"),
                }
                for p in d.persons
            ]
        },
    ),
    AirkeySensorEntityDescription(
        key="cards",
        translation_key="cards",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.cards),
        attrs_fn=lambda d: {
            "cards": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "identifier": c.get("mediumIdentifier"),
                    "activated": c.get("activated"),
                    "person_id": c.get("personId"),
                    "person_name": _person_names_by_id(d.persons).get(
                        c.get("personId")
                    ),
                    "last_used_at": d.medium_last_used.get(c.get("id"), {}).get(
                        "timestamp"
                    ),
                    "last_used_lock_name": d.medium_last_used.get(c.get("id"), {}).get(
                        "lock_name"
                    ),
                }
                for c in d.cards
            ]
        },
    ),
    AirkeySensorEntityDescription(
        key="phones",
        translation_key="phones",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.phones),
        attrs_fn=lambda d: {
            "phones": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "identifier": p.get("mediumIdentifier"),
                    "activated": p.get("activated"),
                    "person_id": p.get("personId"),
                    "person_name": _person_names_by_id(d.persons).get(
                        p.get("personId")
                    ),
                    "last_used_at": d.medium_last_used.get(p.get("id"), {}).get(
                        "timestamp"
                    ),
                    "last_used_lock_name": d.medium_last_used.get(p.get("id"), {}).get(
                        "lock_name"
                    ),
                }
                for p in d.phones
            ]
        },
    ),
    AirkeySensorEntityDescription(
        key="locks",
        translation_key="locks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.locks),
    ),
    AirkeySensorEntityDescription(
        key="areas",
        translation_key="areas",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.areas),
        attrs_fn=lambda d: {
            "areas": [{"id": a.get("id"), "name": a.get("name")} for a in d.areas]
        },
    ),
    AirkeySensorEntityDescription(
        key="authorizations",
        translation_key="authorizations",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.authorizations),
        attrs_fn=lambda d: {"authorizations": _expand_authorizations(d)},
    ),
    AirkeySensorEntityDescription(
        key="blacklist_entries",
        translation_key="blacklist_entries",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.blacklists),
        attrs_fn=lambda d: {"entries": d.blacklists},
    ),
    AirkeySensorEntityDescription(
        key="maintenance_tasks",
        translation_key="maintenance_tasks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.maintenance_tasks),
    ),
    AirkeySensorEntityDescription(
        key="holiday_calendars",
        translation_key="holiday_calendars",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.holiday_calendars),
        attrs_fn=lambda d: {
            "calendars": [
                {"id": c.get("id"), "active": c.get("active")}
                for c in d.holiday_calendars
            ]
        },
    ),
    AirkeySensorEntityDescription(
        key="pending_phone_replacements",
        translation_key="pending_phone_replacements",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.pending_phone_replacements),
    ),
    AirkeySensorEntityDescription(
        key="operators",
        translation_key="operators",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.acos),
    ),
    AirkeySensorEntityDescription(
        key="last_event",
        translation_key="last_event",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (
            dt_util.parse_datetime(d.latest_event["timestamp"])
            if d.latest_event and d.latest_event.get("timestamp")
            else None
        ),
        attrs_fn=lambda d: (
            {"details": d.latest_event.get("details")} if d.latest_event else {}
        ),
    ),
    AirkeySensorEntityDescription(
        key="account",
        translation_key="account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.customer.get("customerNumber"),
        attrs_fn=lambda d: {
            "customer_name": d.customer.get("customerName"),
            "created_on": d.customer.get("createdOn"),
            "two_factor_active": d.settings.get("twoFactorActive"),
            "four_eyes_enabled": d.settings.get("fourEyesEnabled"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirkeyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airkey sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[SensorEntity] = [
        AirkeySensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)

    known_lock_ids: set[int] = set()

    @callback
    def _add_new_locks() -> None:
        new_entities = []
        for lock in coordinator.data.locks:
            lock_id = lock.get("id")
            if lock_id is not None and lock_id not in known_lock_ids:
                known_lock_ids.add(lock_id)
                new_entities.append(AirkeyLockSensor(coordinator, lock_id))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_locks()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_locks))


class AirkeySensor(AirkeyEntity, SensorEntity):
    """Hub-level Airkey sensor driven by a declarative description."""

    entity_description: AirkeySensorEntityDescription

    def __init__(
        self,
        coordinator: AirkeyDataUpdateCoordinator,
        description: AirkeySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class AirkeyLockSensor(AirkeyLockEntity, SensorEntity):
    """Sensor exposing the details of a single Airkey lock."""

    _attr_translation_key = "lock"

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id, "lock")

    @property
    def native_value(self) -> StateType:
        lock = self._get_lock()
        if not lock:
            return None
        door = lock.get("lockDoor") or {}
        return door.get("name") or lock.get("lockIdentifier") or f"Lock {self._lock_id}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lock = self._get_lock() or {}
        door = lock.get("lockDoor") or {}
        firmware = lock.get("lockFirmware") or {}
        last_used = self.coordinator.data.lock_last_used.get(self._lock_id, {})
        return {
            "lock_type": lock.get("lockType"),
            "lock_technology": lock.get("lockTechnology"),
            "ownership": lock.get("ownership"),
            "lock_identifier": lock.get("lockIdentifier"),
            "locking_system_id": lock.get("lockingSystemId"),
            "location": door.get("location"),
            "additional_information": door.get("additionalInformation"),
            "comment": lock.get("comment"),
            "removal_requested": lock.get("removalRequested"),
            "applet_version": firmware.get("appletVersion"),
            "pic_version": firmware.get("picVersion"),
            "motor_pic_version": firmware.get("motorPicVersion"),
            "last_used_at": last_used.get("timestamp"),
            "last_used_by_medium_id": last_used.get("medium_id"),
            "last_used_by_medium_name": last_used.get("medium_name"),
        }
