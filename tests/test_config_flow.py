"""Tests for the Airkey config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.airkey.const import (
    CONF_DAILY_REQUEST_LIMIT,
    CONF_ENVIRONMENT,
    DEFAULT_DAILY_REQUEST_LIMIT,
    DOMAIN,
    ENV_PRODUCTION,
)

from .conftest import API_BASE, register_empty_account


async def test_user_flow_success(hass, aioclient_mock) -> None:
    register_empty_account(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "my-key", CONF_ENVIRONMENT: ENV_PRODUCTION},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Account"
    assert result["data"] == {CONF_API_KEY: "my-key", CONF_ENVIRONMENT: ENV_PRODUCTION}
    assert result["result"].unique_id == "production:CUST-1"
    assert (
        result["result"].options[CONF_DAILY_REQUEST_LIMIT]
        == DEFAULT_DAILY_REQUEST_LIMIT
    )


async def test_user_flow_invalid_auth(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{API_BASE}/customer", status=401)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bad-key", CONF_ENVIRONMENT: ENV_PRODUCTION},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass, aioclient_mock) -> None:
    aioclient_mock.get(f"{API_BASE}/customer", exc=TimeoutError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "my-key", CONF_ENVIRONMENT: ENV_PRODUCTION},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured_aborts(hass, aioclient_mock) -> None:
    register_empty_account(aioclient_mock)

    for _ in range(2):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "my-key", CONF_ENVIRONMENT: ENV_PRODUCTION},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass, aioclient_mock) -> None:
    register_empty_account(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "my-key", CONF_ENVIRONMENT: ENV_PRODUCTION},
    )
    entry = result["result"]
    await hass.async_block_till_done()

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert options_result["type"] is FlowResultType.FORM

    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            "event_lookback_hours": 48,
            CONF_DAILY_REQUEST_LIMIT: 500,
        },
    )

    assert options_result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.options["event_lookback_hours"] == 48
    assert entry.options[CONF_DAILY_REQUEST_LIMIT] == 500
