"""Binary sensors for the EVVA Airkey integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirkeyConfigEntry
from .coordinator import AirkeyData, AirkeyDataUpdateCoordinator
from .entity import AirkeyEntity, AirkeyLockEntity


@dataclass(frozen=True, kw_only=True)
class AirkeyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Airkey hub-level binary sensor."""

    is_on_fn: Callable[[AirkeyData], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[AirkeyBinarySensorEntityDescription, ...] = (
    AirkeyBinarySensorEntityDescription(
        key="maintenance_required",
        translation_key="maintenance_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: len(d.maintenance_tasks) > 0,
    ),
    AirkeyBinarySensorEntityDescription(
        key="pending_phone_replacements",
        translation_key="pending_phone_replacements",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: len(d.pending_phone_replacements) > 0,
    ),
    AirkeyBinarySensorEntityDescription(
        key="two_factor_active",
        translation_key="two_factor_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.settings.get("twoFactorActive")),
    ),
    AirkeyBinarySensorEntityDescription(
        key="four_eyes_enabled",
        translation_key="four_eyes_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.settings.get("fourEyesEnabled")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirkeyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airkey binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[BinarySensorEntity] = [
        AirkeyBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
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
                new_entities.append(
                    AirkeyLockRemovalRequestedSensor(coordinator, lock_id)
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_new_locks()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_locks))


class AirkeyBinarySensor(AirkeyEntity, BinarySensorEntity):
    """Hub-level Airkey binary sensor driven by a declarative description."""

    entity_description: AirkeyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AirkeyDataUpdateCoordinator,
        description: AirkeyBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)


class AirkeyLockRemovalRequestedSensor(AirkeyLockEntity, BinarySensorEntity):
    """Indicates a lock has been marked for removal, pending synchronization."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "removal_requested"

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id, "removal_requested")

    @property
    def is_on(self) -> bool:
        lock = self._get_lock()
        return bool(lock and lock.get("removalRequested"))
