"""Fixtures for the EVVA Airkey test suite."""

from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading in every test."""
    yield


API_BASE = "https://api.airkey.evva.com/cloud/v1"


def register_empty_account(
    aioclient_mock,
    base: str = API_BASE,
    locks: list[dict] | None = None,
    assigned_areas: dict[int, list[dict]] | None = None,
) -> None:
    """Register a full set of empty-but-valid responses for a coordinator refresh.

    aioclient_mock matches a registered URL against the *path* and treats any
    params passed at registration time as a required subset of the request's
    query string, so registering without params matches every page/filter
    variant the API client may request. Pass `locks` to seed a non-empty lock
    list (e.g. to test per-lock usage-history fetches), and `assigned_areas`
    (lock_id -> list of AssignedArea dicts) to override the default empty
    assigned-areas response for specific locks.
    """
    assigned_areas = assigned_areas or {}
    aioclient_mock.get(
        f"{base}/customer",
        json={
            "customerNumber": "CUST-1",
            "accessControlSystemName": "Test Account",
            "customerName": "Test Customer",
            "createdOn": "2020-01-01",
            "correspondenceLanguageCode": "en-UK",
        },
    )
    aioclient_mock.get(
        f"{base}/settings",
        json={"twoFactorActive": False, "fourEyesEnabled": False},
    )
    aioclient_mock.get(f"{base}/acos", json={"acoList": []})
    aioclient_mock.get(f"{base}/areas", json={"offset": 0, "total": 0, "areaList": []})
    aioclient_mock.get(
        f"{base}/locks",
        json={"offset": 0, "total": len(locks or []), "lockList": locks or []},
    )
    for lock in locks or []:
        aioclient_mock.get(
            f"{base}/locks/{lock['id']}/settings/assigned-areas",
            json=assigned_areas.get(lock["id"], []),
        )
        aioclient_mock.get(
            f"{base}/lock-protocol-limit",
            params={"lockId": str(lock["id"])},
            json={"offset": 0, "total": 0, "lockProtocols": []},
        )
    aioclient_mock.get(
        f"{base}/persons", json={"offset": 0, "total": 0, "personList": []}
    )
    aioclient_mock.get(
        f"{base}/media/cards", json={"offset": 0, "total": 0, "mediumList": []}
    )
    aioclient_mock.get(
        f"{base}/media/phones", json={"offset": 0, "total": 0, "mediumList": []}
    )
    aioclient_mock.get(
        f"{base}/authorizations",
        json={"offset": 0, "total": 0, "authorizations": []},
    )
    aioclient_mock.get(f"{base}/blacklists", json=[])
    aioclient_mock.get(
        f"{base}/credits",
        json={"quantityCreditsAmount": 100, "temporalCreditEndOfValidity": None},
    )
    aioclient_mock.get(
        f"{base}/maintenance-tasks",
        json={"offset": 0, "total": 0, "lockMaintenanceTaskList": []},
    )
    aioclient_mock.get(f"{base}/holiday-calendars", json={"holidayCalendarList": []})
    aioclient_mock.get(
        f"{base}/pending-phone-replacements",
        json={"pendingPhoneReplacementList": []},
    )
    aioclient_mock.get(f"{base}/events", json={"offset": 0, "total": 0, "events": []})
