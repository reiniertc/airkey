"""Config flow for the EVVA Airkey integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import AirkeyApiClient, AirkeyAuthError, AirkeyError
from .const import (
    CONF_ENVIRONMENT,
    CONF_EVENT_LOOKBACK_HOURS,
    CONFIG_ENTRY_VERSION,
    DEFAULT_EVENT_LOOKBACK_HOURS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    ENV_PRODUCTION,
    ENVIRONMENTS,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Required(
                CONF_ENVIRONMENT, default=defaults.get(CONF_ENVIRONMENT, ENV_PRODUCTION)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=ENVIRONMENTS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_ENVIRONMENT,
                )
            ),
        }
    )


async def _validate_and_get_customer(
    hass_session: aiohttp.ClientSession, api_key: str, environment: str
) -> dict:
    """Validate credentials and return the customer info, raising on failure."""
    client = AirkeyApiClient(hass_session, api_key, environment)
    return await client.get_customer()


class AirkeyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EVVA Airkey."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    async def _try_connect(
        self, api_key: str, environment: str
    ) -> tuple[dict[str, str], dict | None]:
        """Return (errors, customer). errors is empty on success."""
        session = async_get_clientsession(self.hass)
        try:
            customer = await _validate_and_get_customer(session, api_key, environment)
        except AirkeyAuthError:
            return {"base": "invalid_auth"}, None
        except (TimeoutError, aiohttp.ClientError):
            return {"base": "cannot_connect"}, None
        except AirkeyError:
            _LOGGER.exception("Unexpected Airkey API error during setup")
            return {"base": "unknown"}, None
        return {}, customer

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, customer = await self._try_connect(
                user_input[CONF_API_KEY], user_input[CONF_ENVIRONMENT]
            )
            if not errors and customer is not None:
                await self.async_set_unique_id(
                    f"{user_input[CONF_ENVIRONMENT]}:{customer.get('customerNumber')}"
                )
                self._abort_if_unique_id_configured()
                title = customer.get("accessControlSystemName") or "EVVA Airkey"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_ENVIRONMENT: user_input[CONF_ENVIRONMENT],
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MINUTES,
                        CONF_EVENT_LOOKBACK_HOURS: DEFAULT_EVENT_LOOKBACK_HOURS,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        environment = self._reauth_entry.data[CONF_ENVIRONMENT]

        if user_input is not None:
            errors, customer = await self._try_connect(
                user_input[CONF_API_KEY], environment
            )
            if not errors and customer is not None:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"environment": environment},
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> AirkeyOptionsFlow:
        return AirkeyOptionsFlow()


class AirkeyOptionsFlow(OptionsFlow):
    """Handle Airkey options (polling interval, event lookback)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES,
                        max=1440,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_EVENT_LOOKBACK_HOURS,
                    default=options.get(
                        CONF_EVENT_LOOKBACK_HOURS, DEFAULT_EVENT_LOOKBACK_HOURS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=720,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="h",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
