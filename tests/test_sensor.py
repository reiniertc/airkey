"""Tests for sensor helper logic that doesn't need a running Home Assistant."""

from __future__ import annotations

from custom_components.airkey.coordinator import AirkeyData
from custom_components.airkey.sensor import _expand_authorizations, _medium_person_ids


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


def test_medium_person_ids_covers_cards_and_phones() -> None:
    data = AirkeyData(
        cards=[{"id": 5, "personId": 10}, {"id": 6, "personId": None}],
        phones=[{"id": 7, "personId": 11}],
    )

    result = _medium_person_ids(data)

    assert result == {5: 10, 7: 11}
