"""Tests for sensor helper logic that doesn't need a running Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.airkey.coordinator import AirkeyData
from custom_components.airkey.sensor import (
    SENSOR_DESCRIPTIONS,
    _expand_authorizations,
    _medium_person_ids,
)


def test_expand_authorizations_keeps_direct_lock_authorizations() -> None:
    data = AirkeyData(
        persons=[{"id": 1, "firstName": "Jane", "lastName": "Doe"}],
        authorizations=[
            {
                "id": 10,
                "personId": 1,
                "medium": {"id": 5, "name": "Card A"},
                "lock": {"id": 1, "name": "Front door"},
                "currentState": "UNCHANGED",
            }
        ],
    )

    rows = _expand_authorizations(data)

    assert len(rows) == 1
    assert rows[0]["person_name"] == "Jane Doe"
    assert rows[0]["lock_id"] == 1
    assert rows[0]["lock_name"] == "Front door"


def test_expand_authorizations_expands_area_to_known_locks() -> None:
    data = AirkeyData(
        persons=[{"id": 1, "firstName": "Jane", "lastName": "Doe"}],
        authorizations=[
            {
                "id": 11,
                "personId": 1,
                "medium": {"id": 5, "name": "Card A"},
                "area": {"id": 100, "name": "Garden"},
                "currentState": "UNCHANGED",
            }
        ],
        area_locks={
            100: [
                {"id": 2, "name": "Gate door"},
                {"id": 3, "name": "Shed door"},
            ]
        },
    )

    rows = _expand_authorizations(data)

    lock_names = {row["lock_name"] for row in rows}
    assert lock_names == {"Gate door", "Shed door"}
    assert all(row["person_name"] == "Jane Doe" for row in rows)
    assert all(row["area_name"] == "Garden" for row in rows)


def test_expand_authorizations_keeps_area_only_row_when_locks_unknown() -> None:
    data = AirkeyData(
        persons=[{"id": 1, "firstName": "Jane", "lastName": "Doe"}],
        authorizations=[
            {
                "id": 12,
                "personId": 1,
                "medium": {"id": 5, "name": "Card A"},
                "area": {"id": 999, "name": "Unknown area"},
                "currentState": "UNCHANGED",
            }
        ],
    )

    rows = _expand_authorizations(data)

    assert len(rows) == 1
    assert rows[0]["lock_id"] is None
    assert rows[0]["area_name"] == "Unknown area"


def test_expand_authorizations_prefers_full_lock_and_medium_records() -> None:
    """The authorization's own embedded lock/medium name isn't reliably
    populated by the API - the full Lock/Card/Phone records (from the
    regular /locks and /media/* fetches) must win when available."""
    data = AirkeyData(
        persons=[{"id": 1, "firstName": "Jane", "lastName": "Doe"}],
        locks=[{"id": 1, "lockDoor": {"name": "Kitchen door"}}],
        cards=[{"id": 5, "name": "Card A", "mediumIdentifier": "0005B650"}],
        authorizations=[
            {
                "id": 10,
                "personId": 1,
                # Embedded lock/medium objects with no name, as returned by
                # the API in practice.
                "medium": {"id": 5, "name": None},
                "lock": {"id": 1, "name": None},
                "currentState": "UNCHANGED",
            }
        ],
    )

    rows = _expand_authorizations(data)

    assert len(rows) == 1
    assert rows[0]["lock_name"] == "Kitchen door"
    assert rows[0]["medium_name"] == "Card A"


def _description(key: str):
    return next(d for d in SENSOR_DESCRIPTIONS if d.key == key)


def test_api_requests_today_sensor_reports_limit_and_remaining() -> None:
    data = AirkeyData(request_count_today=40, request_count_limit=250)
    description = _description("api_requests_today")

    assert description.value_fn(data) == 40
    assert description.attrs_fn(data) == {"limit": 250, "remaining": 210}


def test_api_requests_today_sensor_clamps_remaining_at_zero() -> None:
    """If the count somehow exceeds the configured limit (e.g. the limit was
    lowered after requests were already made today), remaining must not go
    negative."""
    data = AirkeyData(request_count_today=260, request_count_limit=250)
    description = _description("api_requests_today")

    assert description.attrs_fn(data) == {"limit": 250, "remaining": 0}


def test_main_data_last_refreshed_sensor_reads_timestamp() -> None:
    now = datetime.now(UTC)
    data = AirkeyData(main_data_last_refreshed=now)

    assert _description("main_data_last_refreshed").value_fn(data) == now


def test_lock_details_last_refreshed_sensor_reads_timestamp() -> None:
    now = datetime.now(UTC)
    data = AirkeyData(lock_details_last_refreshed=now)

    assert _description("lock_details_last_refreshed").value_fn(data) == now


def test_maintenance_tasks_sensor_exposes_task_types_and_lock_name() -> None:
    data = AirkeyData(
        locks=[{"id": 1, "lockDoor": {"name": "Front door"}}],
        maintenance_tasks=[
            {
                "lock": {"id": 1, "name": None},
                "maintenanceTaskList": ["EMPTY_BATTERY", "CLOCK_INVALID"],
            }
        ],
    )
    description = _description("maintenance_tasks")

    assert description.value_fn(data) == 1
    assert description.attrs_fn(data) == {
        "tasks": [
            {
                "lock_id": 1,
                "lock_name": "Front door",
                "types": ["EMPTY_BATTERY", "CLOCK_INVALID"],
            }
        ]
    }


def test_medium_person_ids_covers_cards_and_phones() -> None:
    data = AirkeyData(
        cards=[{"id": 5, "personId": 10}, {"id": 6, "personId": None}],
        phones=[{"id": 7, "personId": 11}],
    )

    result = _medium_person_ids(data)

    assert result == {5: 10, 7: 11}
