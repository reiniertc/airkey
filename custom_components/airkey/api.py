"""Async client for the EVVA Airkey Cloud API.

Covers the full public surface of the EVVA AirKey Cloud API (v18), see
https://integration.api.airkey.evva.com/docs/ for the authoritative reference.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import API_BASE_PATH, HOST_BY_ENVIRONMENT

_LOGGER = logging.getLogger(__name__)

DEFAULT_PAGE_LIMIT = 100
# Safety cap so a single refresh cycle can never spiral into an unbounded
# number of requests against a resource with a huge amount of records.
MAX_PAGES = 20


class AirkeyError(Exception):
    """Base exception for all Airkey API errors."""


class AirkeyAuthError(AirkeyError):
    """The API key is missing, invalid or expired (HTTP 401)."""


class AirkeyForbiddenError(AirkeyError):
    """The API key does not have permission for this operation (HTTP 403).

    This is the expected outcome of any write call when the underlying
    Airkey contract only grants read access.
    """


class AirkeyRateLimitError(AirkeyError):
    """The API rejected the request because of rate limiting (HTTP 429)."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("Airkey API rate limit exceeded")
        self.retry_after = retry_after


class AirkeyApiError(AirkeyError):
    """Any other non-2xx response from the API."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Airkey API error {status}: {message}")
        self.status = status


class AirkeyApiClient:
    """Thin async wrapper around the EVVA Airkey Cloud API."""

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, environment: str
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._environment = environment
        self._host = HOST_BY_ENVIRONMENT[environment]
        self._request_count = 0
        self._request_count_date: str | None = None

    # -- request accounting ----------------------------------------------
    #
    # The Airkey Cloud API enforces an undocumented daily request quota
    # (reported by EVVA support as 250/day, resetting at midnight UTC). This
    # is a local, best-effort count of requests *this client instance* has
    # made today - it can't see requests from elsewhere (another app, a
    # second HA instance) and resets to 0 on process start unless seeded via
    # seed_request_count(), but it's the closest self-monitoring available
    # since Airkey exposes no "requests remaining" endpoint.

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _note_request(self) -> None:
        today = self._today()
        if self._request_count_date != today:
            self._request_count_date = today
            self._request_count = 0
        self._request_count += 1

    @property
    def request_count_today(self) -> int:
        """Number of requests made today (UTC), 0 if none yet today."""
        if self._request_count_date != self._today():
            return 0
        return self._request_count

    @property
    def request_count_date(self) -> str:
        """The UTC date (YYYY-MM-DD) request_count_today applies to."""
        return self._today()

    def seed_request_count(self, count: int, date: str) -> None:
        """Restore a persisted count, e.g. after a Home Assistant restart."""
        if date == self._today():
            self._request_count = count
            self._request_count_date = date

    # -- low level -----------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        self._note_request()
        url = f"https://{self._host}{API_BASE_PATH}{path}"
        headers = {"X-API-Key": self._api_key, "Accept": "application/json"}
        clean_params = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        _LOGGER.debug("Airkey %s %s params=%s", method, path, clean_params)
        async with self._session.request(
            method, url, headers=headers, params=clean_params, json=json_body
        ) as resp:
            if resp.status == 401:
                raise AirkeyAuthError("Invalid or expired Airkey API key")
            if resp.status == 403:
                raise AirkeyForbiddenError(f"Not permitted: {method} {path}")
            if resp.status == 429:
                retry_after_header = resp.headers.get("Retry-After")
                retry_after = float(retry_after_header) if retry_after_header else None
                raise AirkeyRateLimitError(retry_after)
            if resp.status >= 400:
                text = await resp.text()
                raise AirkeyApiError(resp.status, text[:500])
            if resp.status == 204:
                return None
            text = await resp.text()
            if not text:
                return None
            return json.loads(text)

    async def _get_paginated(
        self, path: str, list_key: str, *, params: dict[str, Any] | None = None
    ) -> list[dict]:
        """Fetch every page of an offset/limit paginated list endpoint."""
        results: list[dict] = []
        base_params = dict(params or {})
        offset = 0
        for _ in range(MAX_PAGES):
            page_params = {**base_params, "offset": offset, "limit": DEFAULT_PAGE_LIMIT}
            data = await self._request("GET", path, params=page_params) or {}
            items = data.get(list_key) or []
            results.extend(items)
            total = data.get("total", len(results))
            offset += len(items)
            if not items or offset >= total:
                return results
        _LOGGER.warning(
            "Airkey %s: result truncated after %s pages (safety cap reached)",
            path,
            MAX_PAGES,
        )
        return results

    # -- customer / settings / acos -------------------------------------

    async def get_customer(self) -> dict:
        return await self._request("GET", "/customer")

    async def get_settings(self) -> dict:
        return await self._request("GET", "/settings")

    async def get_acos(self) -> list[dict]:
        data = await self._request("GET", "/acos") or {}
        return data.get("acoList", [])

    async def get_acos_support(self) -> list[dict]:
        data = await self._request("GET", "/acos/support") or {}
        return data.get("acoList", [])

    # -- areas ------------------------------------------------------------

    async def get_areas(self, *, lock_id: int | None = None) -> list[dict]:
        return await self._get_paginated(
            "/areas", "areaList", params={"lockId": lock_id}
        )

    async def get_area(self, area_id: int) -> dict:
        return await self._request("GET", f"/areas/{area_id}")

    # -- locks --------------------------------------------------------------

    async def get_locks(
        self, *, calendar_id: int | None = None, locking_system_id: int | None = None
    ) -> list[dict]:
        return await self._get_paginated(
            "/locks",
            "lockList",
            params={"calendarId": calendar_id, "lockingSystemId": locking_system_id},
        )

    async def get_lock(self, lock_id: int) -> dict:
        return await self._request("GET", f"/locks/{lock_id}")

    async def update_lock(self, lock_id: int, lock: dict) -> dict:
        return await self._request("PUT", f"/locks/{lock_id}", json_body=lock)

    async def remove_lock(self, lock_id: int) -> None:
        await self._request("POST", f"/locks/{lock_id}/remove")

    async def abort_remove_lock(self, lock_id: int) -> None:
        await self._request("POST", f"/locks/{lock_id}/abort-remove")

    async def add_shared_lock(
        self,
        sharing_code: str,
        anonymize_data_in_owner_protocol: bool,
        alternative_door_name: str | None = None,
    ) -> dict:
        body = {
            "sharingCode": sharing_code,
            "anonymizeDataInOwnerProtocol": anonymize_data_in_owner_protocol,
            "alternativeDoorName": alternative_door_name,
        }
        return await self._request("POST", "/locks/add-shared-lock", json_body=body)

    async def get_lock_settings(self, lock_id: int) -> dict:
        return await self._request("GET", f"/locks/{lock_id}/settings")

    async def update_lock_settings(self, lock_id: int, settings: dict) -> dict:
        return await self._request(
            "PUT", f"/locks/{lock_id}/settings", json_body=settings
        )

    async def get_lock_active_shares(self, lock_id: int) -> list[dict]:
        return await self._request("GET", f"/locks/{lock_id}/settings/active-shares")

    async def remove_lock_active_shares(self, lock_id: int, acos: list[str]) -> None:
        await self._request(
            "POST", f"/locks/{lock_id}/settings/active-shares/remove", json_body=acos
        )

    async def get_lock_assigned_areas(self, lock_id: int) -> list[dict]:
        return await self._request("GET", f"/locks/{lock_id}/settings/assigned-areas")

    async def assign_areas_to_lock(self, lock_id: int, area_ids: list[int]) -> None:
        await self._request(
            "POST",
            f"/locks/{lock_id}/settings/assigned-areas/add",
            json_body=area_ids,
        )

    async def unassign_areas_from_lock(self, lock_id: int, area_ids: list[int]) -> None:
        await self._request(
            "POST",
            f"/locks/{lock_id}/settings/assigned-areas/remove",
            json_body=area_ids,
        )

    async def get_lock_sharing_codes(self, lock_id: int) -> list[dict]:
        return await self._request("GET", f"/locks/{lock_id}/settings/sharing-codes")

    async def create_sharing_code(self, lock_id: int) -> dict:
        return await self._request("POST", f"/locks/{lock_id}/settings/sharing-codes")

    async def remove_sharing_code(self, lock_id: int, sharing_code_id: int) -> None:
        await self._request(
            "DELETE", f"/locks/{lock_id}/settings/sharing-codes/{sharing_code_id}"
        )

    # -- persons --------------------------------------------------------------

    async def get_persons(self, *, search: str | None = None) -> list[dict]:
        return await self._get_paginated(
            "/persons", "personList", params={"search": search}
        )

    async def get_person(self, person_id: int) -> dict:
        return await self._request("GET", f"/persons/{person_id}")

    async def create_persons(self, persons: list[dict]) -> list[dict]:
        return await self._request("POST", "/persons", json_body=persons)

    async def update_persons(self, persons: list[dict]) -> list[dict]:
        return await self._request("PUT", "/persons", json_body=persons)

    async def delete_persons(self, person_ids: list[int]) -> None:
        await self._request("DELETE", "/persons", json_body=person_ids)

    # -- media (generic) --------------------------------------------------

    async def get_media(
        self,
        *,
        person_id: int | None = None,
        locking_system_id: int | None = None,
        assignment_status: str | None = None,
    ) -> list[dict]:
        return await self._get_paginated(
            "/media",
            "mediumList",
            params={
                "personId": person_id,
                "lockingSystemId": locking_system_id,
                "assignmentStatus": assignment_status,
            },
        )

    async def get_medium(self, medium_id: int) -> dict:
        return await self._request("GET", f"/media/{medium_id}")

    async def assign_media(self, assignments: list[dict]) -> None:
        await self._request("POST", "/media/assign", json_body=assignments)

    async def cancel_medium_assignment(self, medium_ids: list[int]) -> None:
        await self._request("POST", "/media/cancel-assignment", json_body=medium_ids)

    async def deactivate_medium(
        self, medium_id: int, reason: str, comment: str | None = None
    ) -> dict:
        return await self._request(
            "POST",
            f"/media/{medium_id}/deactivate",
            params={"reason": reason, "comment": comment},
        )

    async def reactivate_medium(
        self,
        medium_id: int,
        reason: str,
        recover_authorizations: bool,
        comment: str | None = None,
    ) -> dict:
        return await self._request(
            "POST",
            f"/media/{medium_id}/reactivate",
            params={
                "reason": reason,
                "comment": comment,
                "recoverAuthorizations": recover_authorizations,
            },
        )

    async def empty_medium(self, medium_id: int) -> dict:
        return await self._request("POST", f"/media/{medium_id}/empty")

    # -- media / cards ------------------------------------------------------

    async def get_cards(self, **filters: Any) -> list[dict]:
        return await self._get_paginated("/media/cards", "mediumList", params=filters)

    async def get_card(self, card_id: int) -> dict:
        return await self._request("GET", f"/media/cards/{card_id}")

    async def update_cards(self, cards: list[dict]) -> list[dict]:
        return await self._request("PUT", "/media/cards", json_body=cards)

    # -- media / phones -------------------------------------------------------

    async def get_phones(self, **filters: Any) -> list[dict]:
        return await self._get_paginated("/media/phones", "mediumList", params=filters)

    async def get_phone(self, phone_id: int) -> dict:
        return await self._request("GET", f"/media/phones/{phone_id}")

    async def add_phones(self, phones: list[dict]) -> list[dict]:
        return await self._request("POST", "/media/phones", json_body=phones)

    async def update_phones(self, phones: list[dict]) -> list[dict]:
        return await self._request("PUT", "/media/phones", json_body=phones)

    async def delete_phones(self, phone_ids: list[int]) -> None:
        await self._request("DELETE", "/media/phones", json_body=phone_ids)

    async def generate_phone_pairing_code(self, phone_id: int) -> dict:
        return await self._request("POST", f"/media/phones/{phone_id}/pairing")

    async def reset_phone_pin(self, phone_id: int) -> dict:
        return await self._request("POST", f"/media/phones/{phone_id}/pin-reset")

    async def send_phone_registration_code_mail(
        self,
        phone_id: int,
        mail_subject: str | None = None,
        mail_text: str | None = None,
    ) -> None:
        body = {"mailSubject": mail_subject, "mailText": mail_text}
        await self._request(
            "POST",
            f"/media/phones/{phone_id}/send-registration-code/mail",
            json_body=body,
        )

    async def send_phone_registration_code_sms(
        self, phone_id: int, sms_text: str | None = None
    ) -> None:
        body = {"smsText": sms_text}
        await self._request(
            "POST",
            f"/media/phones/{phone_id}/send-registration-code/sms",
            json_body=body,
        )

    # -- authorizations -------------------------------------------------------

    async def get_authorizations(self, **filters: Any) -> list[dict]:
        return await self._get_paginated(
            "/authorizations", "authorizations", params=filters
        )

    async def get_authorization(self, authorization_id: int) -> dict:
        return await self._request("GET", f"/authorizations/{authorization_id}")

    async def create_simple_authorization(self, authorization: dict) -> dict:
        return await self._request(
            "POST", "/authorizations/simple", json_body=authorization
        )

    async def create_advanced_authorization(self, authorization_change: dict) -> dict:
        return await self._request(
            "POST", "/authorizations/advanced", json_body=authorization_change
        )

    async def delete_authorizations(self, deletions: list[dict]) -> None:
        await self._request("PUT", "/authorizations", json_body=deletions)

    # -- blacklists / credits / maintenance ------------------------------

    async def get_blacklists(
        self, *, lock_id: int | None = None, medium_id: int | None = None
    ) -> list[dict]:
        return (
            await self._request(
                "GET", "/blacklists", params={"lockId": lock_id, "mediumId": medium_id}
            )
            or []
        )

    async def get_credits(self) -> dict:
        return await self._request("GET", "/credits")

    async def get_credits_protocol(self) -> list[dict]:
        data = await self._request("GET", "/credits-protocol") or {}
        return data.get("creditsProtocolList", [])

    async def get_maintenance_tasks(self, **filters: Any) -> list[dict]:
        return await self._get_paginated(
            "/maintenance-tasks", "lockMaintenanceTaskList", params=filters
        )

    # -- events / protocols -----------------------------------------------

    async def get_events(
        self,
        *,
        created_after: str | None = None,
        event_type: str | None = None,
    ) -> list[dict]:
        return await self._get_paginated(
            "/events",
            "events",
            params={"createdAfter": created_after, "type": event_type},
        )

    async def get_event(self, event_id: int) -> dict:
        return await self._request("GET", f"/events/{event_id}")

    async def get_system_protocol(self, **filters: Any) -> list[dict]:
        return await self._get_paginated(
            "/system-protocol-limit", "systemProtocolList", params=filters
        )

    async def get_medium_protocol(self, **filters: Any) -> list[dict]:
        # The API reuses the same "lockProtocols" wrapper key for both the
        # lock- and medium-protocol endpoints.
        return await self._get_paginated(
            "/medium-protocol-limit", "lockProtocols", params=filters
        )

    async def get_lock_protocol(self, **filters: Any) -> list[dict]:
        return await self._get_paginated(
            "/lock-protocol-limit", "lockProtocols", params=filters
        )

    # -- holiday calendars --------------------------------------------------

    async def get_holiday_calendars(self) -> list[dict]:
        data = await self._request("GET", "/holiday-calendars") or {}
        return data.get("holidayCalendarList", [])

    async def get_holiday_calendar(self, calendar_id: int) -> dict:
        return await self._request("GET", f"/holiday-calendars/{calendar_id}")

    async def set_holiday_calendar_active(
        self, calendar_id: int, calendar: dict
    ) -> dict:
        return await self._request(
            "PUT", f"/holiday-calendars/{calendar_id}", json_body=calendar
        )

    async def get_holiday_calendar_locks(self, calendar_id: int) -> list[dict]:
        return await self._get_paginated(
            f"/holiday-calendars/{calendar_id}/locks", "lockList"
        )

    async def add_holiday_calendar_slot(self, calendar_id: int, slot: dict) -> dict:
        return await self._request(
            "POST", f"/holiday-calendars/{calendar_id}/slots", json_body=slot
        )

    async def get_holiday_calendar_slot(self, calendar_id: int, slot_id: int) -> dict:
        return await self._request(
            "GET", f"/holiday-calendars/{calendar_id}/slots/{slot_id}"
        )

    async def update_holiday_calendar_slot(
        self, calendar_id: int, slot_id: int, slot: dict
    ) -> dict:
        return await self._request(
            "PUT",
            f"/holiday-calendars/{calendar_id}/slots/{slot_id}",
            json_body=slot,
        )

    async def delete_holiday_calendar_slot(
        self, calendar_id: int, slot_id: int, deletion: dict
    ) -> None:
        await self._request(
            "DELETE",
            f"/holiday-calendars/{calendar_id}/slots/{slot_id}",
            json_body=deletion,
        )

    # -- pending phone replacements ------------------------------------

    async def get_pending_phone_replacements(self) -> list[dict]:
        data = await self._request("GET", "/pending-phone-replacements") or {}
        return data.get("pendingPhoneReplacementList", [])

    async def approve_phone_replacement(self, replacement_id: int) -> dict:
        return await self._request(
            "POST", f"/pending-phone-replacements/{replacement_id}/approve"
        )

    async def reject_phone_replacement(self, replacement_id: int) -> dict:
        return await self._request(
            "POST", f"/pending-phone-replacements/{replacement_id}/reject"
        )

    # -- send-a-key ----------------------------------------------------------

    async def send_a_key_mail(self, request_body: dict) -> dict:
        return await self._request("POST", "/send-a-key/mail", json_body=request_body)

    async def send_a_key_sms(self, request_body: dict) -> dict:
        return await self._request("POST", "/send-a-key/sms", json_body=request_body)

    # -- test environment only -----------------------------------------

    async def reset_test_data(self) -> None:
        await self._request("POST", "/public-mgmt/reset-test-data")
