"""DataUpdateCoordinator for the EVVA Airkey integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AirkeyApiClient, AirkeyAuthError, AirkeyError, AirkeyRateLimitError
from .const import (
    CONF_EVENT_LOOKBACK_HOURS,
    CONF_LOCK_DETAILS_INTERVAL_HOURS,
    DEFAULT_EVENT_LOOKBACK_HOURS,
    DEFAULT_LOCK_DETAILS_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    LOCK_PROTOCOL_LOOKBACK_DAYS,
    MIN_LOCK_DETAILS_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_MINUTES,
    SUCCESSFUL_UNLOCK_EVENT_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class AirkeyData:
    """Snapshot of all Airkey resources fetched during one coordinator refresh."""

    customer: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    acos: list[dict] = field(default_factory=list)
    areas: list[dict] = field(default_factory=list)
    locks: list[dict] = field(default_factory=list)
    persons: list[dict] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)
    phones: list[dict] = field(default_factory=list)
    authorizations: list[dict] = field(default_factory=list)
    blacklists: list[dict] = field(default_factory=list)
    credits: dict = field(default_factory=dict)
    maintenance_tasks: list[dict] = field(default_factory=list)
    holiday_calendars: list[dict] = field(default_factory=list)
    pending_phone_replacements: list[dict] = field(default_factory=list)
    new_events: list[dict] = field(default_factory=list)
    latest_event: dict | None = None
    # lock_id -> {"timestamp", "medium_id", "medium_name", "event_type"}
    lock_last_used: dict[int, dict] = field(default_factory=dict)
    # medium_id -> {"timestamp", "lock_id", "lock_name", "event_type"}
    medium_last_used: dict[int, dict] = field(default_factory=dict)
    # area_id -> [{"id": lock_id, "name": lock_name}, ...]
    area_locks: dict[int, list[dict]] = field(default_factory=dict)


class AirkeyDataUpdateCoordinator(DataUpdateCoordinator[AirkeyData]):
    """Fetch all monitored Airkey resources on a single, shared interval."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: AirkeyApiClient
    ) -> None:
        self.entry = entry
        self.client = client
        self._last_event_poll: str | None = None
        self._last_lock_details_poll: datetime | None = None
        self._force_lock_details_refresh = False

        scan_minutes = max(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
            MIN_SCAN_INTERVAL_MINUTES,
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_minutes),
        )

    async def async_refresh_lock_details(self) -> None:
        """Force an immediate refresh of the per-lock usage/area data.

        Normally these are only refreshed on their own (much longer) interval
        to limit how many extra API calls a refresh cycle costs.
        """
        self._force_lock_details_refresh = True
        await self.async_request_refresh()

    async def _async_update_data(self) -> AirkeyData:
        if self._last_event_poll:
            created_after = self._last_event_poll
        else:
            lookback_hours = self.entry.options.get(
                CONF_EVENT_LOOKBACK_HOURS, DEFAULT_EVENT_LOOKBACK_HOURS
            )
            created_after = _iso(datetime.now(UTC) - timedelta(hours=lookback_hours))

        try:
            customer = await self.client.get_customer()
            settings = await self.client.get_settings()
            acos = await self.client.get_acos()
            areas = await self.client.get_areas()
            locks = await self.client.get_locks()
            persons = await self.client.get_persons()
            cards = await self.client.get_cards()
            phones = await self.client.get_phones()
            authorizations = await self.client.get_authorizations()
            blacklists = await self.client.get_blacklists()
            credits_info = await self.client.get_credits()
            maintenance_tasks = await self.client.get_maintenance_tasks()
            holiday_calendars = await self.client.get_holiday_calendars()
            pending_replacements = await self.client.get_pending_phone_replacements()
            events = await self.client.get_events(created_after=created_after)
        except AirkeyAuthError as err:
            raise ConfigEntryAuthFailed("Airkey API key is invalid or expired") from err
        except AirkeyRateLimitError as err:
            raise UpdateFailed(
                f"Rate limited by the Airkey API (retry after {err.retry_after}s)"
            ) from err
        except AirkeyError as err:
            raise UpdateFailed(str(err)) from err

        self._last_event_poll = _iso(datetime.now(UTC))

        latest_event = self.data.latest_event if self.data else None
        if events:
            latest_event = max(events, key=lambda event: event.get("timestamp") or "")

        lock_details_interval = timedelta(
            hours=max(
                self.entry.options.get(
                    CONF_LOCK_DETAILS_INTERVAL_HOURS,
                    DEFAULT_LOCK_DETAILS_INTERVAL_HOURS,
                ),
                MIN_LOCK_DETAILS_INTERVAL_HOURS,
            )
        )
        now = datetime.now(UTC)
        should_refresh_lock_details = (
            self._force_lock_details_refresh
            or self._last_lock_details_poll is None
            or now - self._last_lock_details_poll >= lock_details_interval
        )

        if should_refresh_lock_details:
            lock_last_used, medium_last_used = await self._async_fetch_last_used(locks)
            area_locks = await self._async_fetch_area_locks(locks)
            self._last_lock_details_poll = now
            self._force_lock_details_refresh = False
        else:
            lock_last_used = self.data.lock_last_used if self.data else {}
            medium_last_used = self.data.medium_last_used if self.data else {}
            area_locks = self.data.area_locks if self.data else {}

        return AirkeyData(
            customer=customer or {},
            settings=settings or {},
            acos=acos,
            areas=areas,
            locks=locks,
            persons=persons,
            cards=cards,
            phones=phones,
            authorizations=authorizations,
            blacklists=blacklists,
            credits=credits_info or {},
            maintenance_tasks=maintenance_tasks,
            holiday_calendars=holiday_calendars,
            pending_phone_replacements=pending_replacements,
            new_events=events,
            latest_event=latest_event,
            lock_last_used=lock_last_used,
            medium_last_used=medium_last_used,
            area_locks=area_locks,
        )

    async def _async_fetch_last_used(
        self, locks: list[dict]
    ) -> tuple[dict[int, dict], dict[int, dict]]:
        """Determine the last successful unlock per lock (and, inverted, per medium).

        Queried per lock (the lock-protocol-limit endpoint doesn't expose a lock
        reference on unfiltered entries) and bounded to a recent window so the
        result is complete rather than truncated by the pagination safety cap.
        """
        since = _iso(datetime.now(UTC) - timedelta(days=LOCK_PROTOCOL_LOOKBACK_DAYS))
        lock_last_used: dict[int, dict] = {}

        for lock in locks:
            lock_id = lock.get("id")
            if lock_id is None:
                continue
            try:
                entries = await self.client.get_lock_protocol(
                    **{"lockId": lock_id, "from": since}
                )
            except AirkeyRateLimitError:
                _LOGGER.warning(
                    "Airkey API rate limited while fetching lock-usage history; "
                    "skipping remaining locks this cycle"
                )
                break
            except AirkeyError as err:
                _LOGGER.debug(
                    "Could not fetch usage history for lock %s: %s", lock_id, err
                )
                continue

            latest: dict | None = None
            for entry in entries:
                event_type = (entry.get("event") or {}).get("type")
                if event_type not in SUCCESSFUL_UNLOCK_EVENT_TYPES:
                    continue
                if latest is None or (entry.get("timestamp") or "") > (
                    latest.get("timestamp") or ""
                ):
                    latest = entry

            if latest is not None:
                medium = latest.get("medium") or {}
                lock_last_used[lock_id] = {
                    "timestamp": latest.get("timestamp"),
                    "medium_id": medium.get("id"),
                    "medium_name": medium.get("name") or medium.get("mediumIdentifier"),
                    "event_type": (latest.get("event") or {}).get("type"),
                }

        lock_by_id = {lock.get("id"): lock for lock in locks}
        medium_last_used: dict[int, dict] = {}
        for lock_id, usage in lock_last_used.items():
            medium_id = usage.get("medium_id")
            if medium_id is None:
                continue
            door = lock_by_id.get(lock_id, {}).get("lockDoor") or {}
            medium_last_used[medium_id] = {
                "timestamp": usage["timestamp"],
                "lock_id": lock_id,
                "lock_name": door.get("name") or door.get("alternativeName"),
                "event_type": usage.get("event_type"),
            }

        return lock_last_used, medium_last_used

    async def _async_fetch_area_locks(self, locks: list[dict]) -> dict[int, list[dict]]:
        """Build a reverse index of area_id -> the locks assigned to that area.

        There is no bulk "locks per area" endpoint, only a per-lock
        "assigned areas" one, so this is queried per lock and inverted.
        """
        area_locks: dict[int, list[dict]] = {}

        for lock in locks:
            lock_id = lock.get("id")
            if lock_id is None:
                continue
            door = lock.get("lockDoor") or {}
            lock_name = (
                door.get("name") or door.get("alternativeName") or f"Lock {lock_id}"
            )
            try:
                assigned_areas = await self.client.get_lock_assigned_areas(lock_id)
            except AirkeyRateLimitError:
                _LOGGER.warning(
                    "Airkey API rate limited while fetching area assignments; "
                    "skipping remaining locks this cycle"
                )
                break
            except AirkeyError as err:
                _LOGGER.debug(
                    "Could not fetch assigned areas for lock %s: %s", lock_id, err
                )
                continue

            for area in assigned_areas:
                area_id = area.get("id")
                if area_id is None:
                    continue
                area_locks.setdefault(area_id, []).append(
                    {"id": lock_id, "name": lock_name}
                )

        return area_locks
