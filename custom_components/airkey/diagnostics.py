"""Diagnostics support for the EVVA Airkey integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import AirkeyConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirkeyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for an Airkey config entry."""
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator_data": asdict(coordinator.data) if coordinator.data else None,
        "last_update_success": coordinator.last_update_success,
    }
