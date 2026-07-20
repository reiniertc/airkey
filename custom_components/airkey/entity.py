"""Base entities for the EVVA Airkey integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirkeyDataUpdateCoordinator


class AirkeyEntity(CoordinatorEntity[AirkeyDataUpdateCoordinator]):
    """Base entity tied to the hub (account-level) device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirkeyDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key

    @property
    def available(self) -> bool:
        # Keep showing the last known good data through a transient API failure
        # (e.g. hitting Airkey's daily rate limit) instead of going unavailable -
        # only actually unavailable before the very first successful refresh.
        return self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        # Fixed device name (rather than the account's own accessControlSystemName) so
        # generated entity_ids are stable, e.g. sensor.airkey_persons. The account name
        # itself is still available on the "account" sensor's attributes.
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="Airkey",
            manufacturer=MANUFACTURER,
            model="Airkey Cloud API",
            configuration_url="https://airkey.evva.com",
        )


class AirkeyLockEntity(CoordinatorEntity[AirkeyDataUpdateCoordinator]):
    """Base entity tied to a single Airkey lock device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirkeyDataUpdateCoordinator, lock_id: int, key: str
    ) -> None:
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_lock_{lock_id}_{key}"
        self._attr_translation_key = key

    def _get_lock(self) -> dict | None:
        if not self.coordinator.data:
            return None
        for lock in self.coordinator.data.locks:
            if lock.get("id") == self._lock_id:
                return lock
        return None

    @property
    def available(self) -> bool:
        # See AirkeyEntity.available - keep showing last known good data through
        # a transient API failure instead of going unavailable.
        return self.coordinator.data is not None and self._get_lock() is not None

    @property
    def device_info(self) -> DeviceInfo:
        lock = self._get_lock() or {}
        door = lock.get("lockDoor") or {}
        door_name = (
            door.get("name") or door.get("alternativeName") or f"Lock {self._lock_id}"
        )
        return DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.entry.entry_id}_lock_{self._lock_id}")
            },
            name=f"Airkey {door_name}",
            manufacturer=MANUFACTURER,
            model=lock.get("lockTechnology") or "Airkey lock",
            via_device=(DOMAIN, self.coordinator.entry.entry_id),
        )
