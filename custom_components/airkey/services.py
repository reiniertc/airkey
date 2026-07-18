"""Services for the EVVA Airkey integration.

Every service maps 1:1 (or close to it) onto a write endpoint of the Airkey
Cloud API. Endpoints that natively accept a batch (e.g. create/update/delete
persons) are exposed as single-item services for automation-friendliness -
the client wraps the single item into the one-element list the API expects.

A handful of deeply nested request bodies (advanced authorizations, holiday
calendar recurrence series, office-mode slots) are exposed as raw ``object``
fields instead of a large tree of scalar fields; their shape follows the
Airkey API reference (https://integration.api.airkey.evva.com/docs/)
1:1 and is documented in services.yaml.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir

from .api import AirkeyError, AirkeyForbiddenError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    ENV_TEST,
    ISSUE_WRITE_ACCESS_DENIED,
    SERVICE_ABORT_REMOVE_LOCK,
    SERVICE_ADD_HOLIDAY_CALENDAR_SLOT,
    SERVICE_ADD_PHONE,
    SERVICE_ADD_SHARED_LOCK,
    SERVICE_APPROVE_PHONE_REPLACEMENT,
    SERVICE_ASSIGN_AREAS_TO_LOCK,
    SERVICE_ASSIGN_MEDIUM,
    SERVICE_CANCEL_MEDIUM_ASSIGNMENT,
    SERVICE_CREATE_ADVANCED_AUTHORIZATION,
    SERVICE_CREATE_PERSON,
    SERVICE_CREATE_SHARING_CODE,
    SERVICE_CREATE_SIMPLE_AUTHORIZATION,
    SERVICE_DEACTIVATE_MEDIUM,
    SERVICE_DELETE_AUTHORIZATION,
    SERVICE_DELETE_HOLIDAY_CALENDAR_SLOT,
    SERVICE_DELETE_PERSON,
    SERVICE_DELETE_PHONE,
    SERVICE_EMPTY_MEDIUM,
    SERVICE_GENERATE_PHONE_PAIRING_CODE,
    SERVICE_REACTIVATE_MEDIUM,
    SERVICE_REFRESH,
    SERVICE_REFRESH_LOCK_DETAILS,
    SERVICE_REJECT_PHONE_REPLACEMENT,
    SERVICE_REMOVE_ACTIVE_SHARES,
    SERVICE_REMOVE_LOCK,
    SERVICE_REMOVE_SHARING_CODE,
    SERVICE_RESET_PHONE_PIN,
    SERVICE_RESET_TEST_DATA,
    SERVICE_SEND_A_KEY_MAIL,
    SERVICE_SEND_A_KEY_SMS,
    SERVICE_SEND_REGISTRATION_CODE_MAIL,
    SERVICE_SEND_REGISTRATION_CODE_SMS,
    SERVICE_SET_HOLIDAY_CALENDAR_ACTIVE,
    SERVICE_UNASSIGN_AREAS_FROM_LOCK,
    SERVICE_UPDATE_CARD,
    SERVICE_UPDATE_HOLIDAY_CALENDAR_SLOT,
    SERVICE_UPDATE_LOCK,
    SERVICE_UPDATE_LOCK_SETTINGS,
    SERVICE_UPDATE_PERSON,
    SERVICE_UPDATE_PHONE,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})


def _get_entry(hass: HomeAssistant, call: ServiceCall):
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(f"Unknown Airkey config entry: {entry_id}")
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(f"Airkey config entry {entry_id} is not loaded")
    return entry


async def _run(
    hass: HomeAssistant, call: ServiceCall, coro_fn, *, refresh: bool = False
):
    """Look up the entry for `call`, run `coro_fn(entry)` with error handling."""
    entry = _get_entry(hass, call)
    client = entry.runtime_data.client
    try:
        result = await coro_fn(entry, client)
    except AirkeyForbiddenError as err:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_WRITE_ACCESS_DENIED}_{entry.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_WRITE_ACCESS_DENIED,
            translation_placeholders={"title": entry.title},
        )
        raise HomeAssistantError(
            f"The Airkey API key for '{entry.title}' does not have write access "
            f"for {call.service}"
        ) from err
    except AirkeyError as err:
        raise HomeAssistantError(str(err)) from err

    if refresh:
        await entry.runtime_data.coordinator.async_request_refresh()
    return result


def _strip_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register all Airkey services. Called once when the integration loads."""

    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return  # already registered (multiple config entries)

    async def handle_refresh(call: ServiceCall) -> None:
        entry = _get_entry(hass, call)
        await entry.runtime_data.coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, handle_refresh, schema=BASE_SCHEMA
    )

    async def handle_refresh_lock_details(call: ServiceCall) -> None:
        entry = _get_entry(hass, call)
        await entry.runtime_data.coordinator.async_refresh_lock_details()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_LOCK_DETAILS,
        handle_refresh_lock_details,
        schema=BASE_SCHEMA,
    )

    async def handle_reset_test_data(call: ServiceCall) -> None:
        entry = _get_entry(hass, call)
        if entry.data.get("environment") != ENV_TEST:
            raise ServiceValidationError(
                "reset_test_data is only available for config entries using the "
                "test/integration environment"
            )
        await _run(hass, call, lambda e, c: c.reset_test_data(), refresh=True)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET_TEST_DATA, handle_reset_test_data, schema=BASE_SCHEMA
    )

    # -- persons ---------------------------------------------------------

    async def handle_create_person(call: ServiceCall) -> None:
        person = _strip_none(
            {
                "firstName": call.data["first_name"],
                "lastName": call.data["last_name"],
                "correspondenceLanguageCode": call.data["correspondence_language_code"],
                "secondaryIdentification": call.data.get("secondary_identification"),
                "gender": call.data.get("gender"),
                "birthday": call.data.get("birthday"),
                "phone": call.data.get("phone"),
                "emailAddress": call.data.get("email_address"),
                "street": call.data.get("street"),
                "postalCode": call.data.get("postal_code"),
                "city": call.data.get("city"),
                "countryCode": call.data.get("country_code"),
                "comment": call.data.get("comment"),
            }
        )
        await _run(hass, call, lambda e, c: c.create_persons([person]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_PERSON,
        handle_create_person,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("first_name"): cv.string,
                vol.Required("last_name"): cv.string,
                vol.Required("correspondence_language_code"): cv.string,
                vol.Optional("secondary_identification"): cv.string,
                vol.Optional("gender"): vol.In(["MALE", "FEMALE"]),
                vol.Optional("birthday"): cv.string,
                vol.Optional("phone"): cv.string,
                vol.Optional("email_address"): cv.string,
                vol.Optional("street"): cv.string,
                vol.Optional("postal_code"): cv.string,
                vol.Optional("city"): cv.string,
                vol.Optional("country_code"): cv.string,
                vol.Optional("comment"): cv.string,
            }
        ),
    )

    async def handle_update_person(call: ServiceCall) -> None:
        person = _strip_none(
            {
                "id": call.data["person_id"],
                "version": call.data["version"],
                "firstName": call.data.get("first_name"),
                "lastName": call.data.get("last_name"),
                "correspondenceLanguageCode": call.data.get(
                    "correspondence_language_code"
                ),
                "secondaryIdentification": call.data.get("secondary_identification"),
                "gender": call.data.get("gender"),
                "birthday": call.data.get("birthday"),
                "phone": call.data.get("phone"),
                "emailAddress": call.data.get("email_address"),
                "street": call.data.get("street"),
                "postalCode": call.data.get("postal_code"),
                "city": call.data.get("city"),
                "countryCode": call.data.get("country_code"),
                "comment": call.data.get("comment"),
            }
        )
        await _run(hass, call, lambda e, c: c.update_persons([person]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PERSON,
        handle_update_person,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("person_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Optional("first_name"): cv.string,
                vol.Optional("last_name"): cv.string,
                vol.Optional("correspondence_language_code"): cv.string,
                vol.Optional("secondary_identification"): cv.string,
                vol.Optional("gender"): vol.In(["MALE", "FEMALE"]),
                vol.Optional("birthday"): cv.string,
                vol.Optional("phone"): cv.string,
                vol.Optional("email_address"): cv.string,
                vol.Optional("street"): cv.string,
                vol.Optional("postal_code"): cv.string,
                vol.Optional("city"): cv.string,
                vol.Optional("country_code"): cv.string,
                vol.Optional("comment"): cv.string,
            }
        ),
    )

    async def handle_delete_person(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.delete_persons([call.data["person_id"]]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PERSON,
        handle_delete_person,
        schema=BASE_SCHEMA.extend({vol.Required("person_id"): cv.positive_int}),
    )

    # -- authorizations ---------------------------------------------------

    async def handle_create_simple_authorization(call: ServiceCall) -> None:
        body = _strip_none(
            {
                "mediumId": call.data["medium_id"],
                "lockId": call.data.get("lock_id"),
                "areaId": call.data.get("area_id"),
                "removeAllExistingAuthorizationsForPair": call.data.get(
                    "remove_all_existing_authorizations_for_pair"
                ),
                "pushMessage": call.data.get("push_message"),
                "authorizationInfo": call.data["authorization_info"],
            }
        )
        await _run(
            hass, call, lambda e, c: c.create_simple_authorization(body), refresh=True
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SIMPLE_AUTHORIZATION,
        handle_create_simple_authorization,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Optional("lock_id"): cv.positive_int,
                vol.Optional("area_id"): cv.positive_int,
                vol.Optional("remove_all_existing_authorizations_for_pair"): cv.boolean,
                vol.Optional("push_message"): cv.string,
                vol.Required("authorization_info"): dict,
            }
        ),
    )

    async def handle_create_advanced_authorization(call: ServiceCall) -> None:
        body = _strip_none(
            {
                "authorizationCreateList": call.data.get(
                    "authorization_create_list", []
                ),
                "authorizationUpdateList": call.data.get(
                    "authorization_update_list", []
                ),
                "pushMessage": call.data.get("push_message"),
            }
        )
        await _run(
            hass, call, lambda e, c: c.create_advanced_authorization(body), refresh=True
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ADVANCED_AUTHORIZATION,
        handle_create_advanced_authorization,
        schema=BASE_SCHEMA.extend(
            {
                vol.Optional("authorization_create_list"): [dict],
                vol.Optional("authorization_update_list"): [dict],
                vol.Optional("push_message"): cv.string,
            }
        ),
    )

    async def handle_delete_authorization(call: ServiceCall) -> None:
        deletion = {
            "id": call.data["authorization_id"],
            "deletionRequested": call.data.get("deletion_requested", True),
        }
        await _run(
            hass, call, lambda e, c: c.delete_authorizations([deletion]), refresh=True
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_AUTHORIZATION,
        handle_delete_authorization,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("authorization_id"): cv.positive_int,
                vol.Optional("deletion_requested", default=True): cv.boolean,
            }
        ),
    )

    # -- media --------------------------------------------------------------

    async def handle_assign_medium(call: ServiceCall) -> None:
        assignment = {
            "mediumId": call.data["medium_id"],
            "personId": call.data["person_id"],
        }
        await _run(hass, call, lambda e, c: c.assign_media([assignment]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_MEDIUM,
        handle_assign_medium,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Required("person_id"): cv.positive_int,
            }
        ),
    )

    async def handle_cancel_medium_assignment(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.cancel_medium_assignment([call.data["medium_id"]]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_MEDIUM_ASSIGNMENT,
        handle_cancel_medium_assignment,
        schema=BASE_SCHEMA.extend({vol.Required("medium_id"): cv.positive_int}),
    )

    async def handle_deactivate_medium(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.deactivate_medium(
                call.data["medium_id"], call.data["reason"], call.data.get("comment")
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_MEDIUM,
        handle_deactivate_medium,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Required("reason"): cv.string,
                vol.Optional("comment"): cv.string,
            }
        ),
    )

    async def handle_reactivate_medium(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.reactivate_medium(
                call.data["medium_id"],
                call.data["reason"],
                call.data.get("recover_authorizations", False),
                call.data.get("comment"),
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REACTIVATE_MEDIUM,
        handle_reactivate_medium,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Required("reason"): cv.string,
                vol.Optional("recover_authorizations", default=False): cv.boolean,
                vol.Optional("comment"): cv.string,
            }
        ),
    )

    async def handle_empty_medium(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.empty_medium(call.data["medium_id"]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EMPTY_MEDIUM,
        handle_empty_medium,
        schema=BASE_SCHEMA.extend({vol.Required("medium_id"): cv.positive_int}),
    )

    async def handle_update_card(call: ServiceCall) -> None:
        card = _strip_none(
            {
                "id": call.data["medium_id"],
                "version": call.data["version"],
                "name": call.data.get("name"),
                "comment": call.data.get("comment"),
                "releaseDurationExtended": call.data.get("release_duration_extended"),
                "permanentOpeningEnabled": call.data.get("permanent_opening_enabled"),
            }
        )
        await _run(hass, call, lambda e, c: c.update_cards([card]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CARD,
        handle_update_card,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Optional("name"): cv.string,
                vol.Optional("comment"): cv.string,
                vol.Optional("release_duration_extended"): cv.boolean,
                vol.Optional("permanent_opening_enabled"): cv.boolean,
            }
        ),
    )

    # -- phones -----------------------------------------------------------

    async def handle_add_phone(call: ServiceCall) -> None:
        phone = _strip_none(
            {"phoneNumber": call.data["phone_number"], "name": call.data.get("name")}
        )
        await _run(hass, call, lambda e, c: c.add_phones([phone]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PHONE,
        handle_add_phone,
        schema=BASE_SCHEMA.extend(
            {vol.Required("phone_number"): cv.string, vol.Optional("name"): cv.string}
        ),
    )

    async def handle_update_phone(call: ServiceCall) -> None:
        phone = _strip_none(
            {
                "id": call.data["medium_id"],
                "version": call.data["version"],
                "phoneNumber": call.data.get("phone_number"),
                "name": call.data.get("name"),
                "comment": call.data.get("comment"),
                "releaseDurationExtended": call.data.get("release_duration_extended"),
                "permanentOpeningEnabled": call.data.get("permanent_opening_enabled"),
                "phoneSettings": _strip_none(
                    {
                        "inMaintenanceMode": call.data.get("in_maintenance_mode"),
                        "mediumLogVisible": call.data.get("medium_log_visible"),
                    }
                )
                or None,
            }
        )
        await _run(hass, call, lambda e, c: c.update_phones([phone]), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PHONE,
        handle_update_phone,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Optional("phone_number"): cv.string,
                vol.Optional("name"): cv.string,
                vol.Optional("comment"): cv.string,
                vol.Optional("release_duration_extended"): cv.boolean,
                vol.Optional("permanent_opening_enabled"): cv.boolean,
                vol.Optional("in_maintenance_mode"): cv.boolean,
                vol.Optional("medium_log_visible"): cv.boolean,
            }
        ),
    )

    async def handle_delete_phone(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.delete_phones([call.data["medium_id"]]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PHONE,
        handle_delete_phone,
        schema=BASE_SCHEMA.extend({vol.Required("medium_id"): cv.positive_int}),
    )

    async def handle_generate_phone_pairing_code(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.generate_phone_pairing_code(call.data["medium_id"]),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_PHONE_PAIRING_CODE,
        handle_generate_phone_pairing_code,
        schema=BASE_SCHEMA.extend({vol.Required("medium_id"): cv.positive_int}),
    )

    async def handle_reset_phone_pin(call: ServiceCall) -> None:
        await _run(hass, call, lambda e, c: c.reset_phone_pin(call.data["medium_id"]))

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_PHONE_PIN,
        handle_reset_phone_pin,
        schema=BASE_SCHEMA.extend({vol.Required("medium_id"): cv.positive_int}),
    )

    async def handle_send_registration_code_mail(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.send_phone_registration_code_mail(
                call.data["medium_id"],
                call.data.get("mail_subject"),
                call.data.get("mail_text"),
            ),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_REGISTRATION_CODE_MAIL,
        handle_send_registration_code_mail,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Optional("mail_subject"): cv.string,
                vol.Optional("mail_text"): cv.string,
            }
        ),
    )

    async def handle_send_registration_code_sms(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.send_phone_registration_code_sms(
                call.data["medium_id"], call.data.get("sms_text")
            ),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_REGISTRATION_CODE_SMS,
        handle_send_registration_code_sms,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("medium_id"): cv.positive_int,
                vol.Optional("sms_text"): cv.string,
            }
        ),
    )

    # -- send-a-key -------------------------------------------------------

    async def handle_send_a_key_mail(call: ServiceCall) -> None:
        body = _strip_none(
            {
                "phone": {"phoneNumber": call.data["phone_number"]},
                "person": {
                    "firstName": call.data["first_name"],
                    "lastName": call.data["last_name"],
                    "emailAddress": call.data["email_address"],
                    "correspondenceLanguageCode": call.data[
                        "correspondence_language_code"
                    ],
                },
                "authorization": call.data.get("authorization"),
                "mailSubject": call.data.get("mail_subject"),
                "mailText": call.data.get("mail_text"),
            }
        )
        await _run(hass, call, lambda e, c: c.send_a_key_mail(body), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_A_KEY_MAIL,
        handle_send_a_key_mail,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("phone_number"): cv.string,
                vol.Required("first_name"): cv.string,
                vol.Required("last_name"): cv.string,
                vol.Required("email_address"): cv.string,
                vol.Required("correspondence_language_code"): cv.string,
                vol.Optional("authorization"): dict,
                vol.Optional("mail_subject"): cv.string,
                vol.Optional("mail_text"): cv.string,
            }
        ),
    )

    async def handle_send_a_key_sms(call: ServiceCall) -> None:
        body = _strip_none(
            {
                "phone": {"phoneNumber": call.data["phone_number"]},
                "person": call.data.get("person"),
                "authorization": call.data.get("authorization"),
                "smsText": call.data.get("sms_text"),
            }
        )
        await _run(hass, call, lambda e, c: c.send_a_key_sms(body), refresh=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_A_KEY_SMS,
        handle_send_a_key_sms,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("phone_number"): cv.string,
                vol.Optional("person"): dict,
                vol.Optional("authorization"): dict,
                vol.Optional("sms_text"): cv.string,
            }
        ),
    )

    # -- locks --------------------------------------------------------------

    async def handle_update_lock(call: ServiceCall) -> None:
        lock = _strip_none(
            {
                "id": call.data["lock_id"],
                "version": call.data["version"],
                "comment": call.data.get("comment"),
                "lockDoor": _strip_none(
                    {
                        "name": call.data.get("door_name"),
                        "additionalInformation": call.data.get(
                            "additional_information"
                        ),
                        "location": call.data.get("location"),
                        "alternativeName": call.data.get("alternative_name"),
                    }
                )
                or None,
            }
        )
        await _run(
            hass,
            call,
            lambda e, c: c.update_lock(call.data["lock_id"], lock),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_LOCK,
        handle_update_lock,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Optional("comment"): cv.string,
                vol.Optional("door_name"): cv.string,
                vol.Optional("additional_information"): cv.string,
                vol.Optional("location"): cv.string,
                vol.Optional("alternative_name"): cv.string,
            }
        ),
    )

    async def handle_remove_lock(call: ServiceCall) -> None:
        await _run(
            hass, call, lambda e, c: c.remove_lock(call.data["lock_id"]), refresh=True
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_LOCK,
        handle_remove_lock,
        schema=BASE_SCHEMA.extend({vol.Required("lock_id"): cv.positive_int}),
    )

    async def handle_abort_remove_lock(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.abort_remove_lock(call.data["lock_id"]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ABORT_REMOVE_LOCK,
        handle_abort_remove_lock,
        schema=BASE_SCHEMA.extend({vol.Required("lock_id"): cv.positive_int}),
    )

    async def handle_update_lock_settings(call: ServiceCall) -> None:
        settings = _strip_none(
            {
                "id": call.data["lock_id"],
                "version": call.data["version"],
                "timezone": call.data.get("timezone"),
                "holidayCalendarEnabled": call.data.get("holiday_calendar_enabled"),
                "manualOfficeModeEnabled": call.data.get("manual_office_mode_enabled"),
                "automaticOfficeModeEnabled": call.data.get(
                    "automatic_office_mode_enabled"
                ),
                "normalReleaseDuration": call.data.get("normal_release_duration"),
                "extendedReleaseDuration": call.data.get("extended_release_duration"),
                "unlockSyncMode": call.data.get("unlock_sync_mode"),
                "rs485LogOutputEnabled": call.data.get("rs485_log_output_enabled"),
                "allowHandsfreeMode": call.data.get("allow_handsfree_mode"),
                "anonymizeDataInOwnerProtocol": call.data.get(
                    "anonymize_data_in_owner_protocol"
                ),
            }
        )
        await _run(
            hass,
            call,
            lambda e, c: c.update_lock_settings(call.data["lock_id"], settings),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_LOCK_SETTINGS,
        handle_update_lock_settings,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Optional("timezone"): cv.string,
                vol.Optional("holiday_calendar_enabled"): cv.boolean,
                vol.Optional("manual_office_mode_enabled"): cv.boolean,
                vol.Optional("automatic_office_mode_enabled"): cv.boolean,
                vol.Optional("normal_release_duration"): cv.positive_int,
                vol.Optional("extended_release_duration"): cv.positive_int,
                vol.Optional("unlock_sync_mode"): vol.In(
                    ["ALWAYS", "PERIODICALLY", "NEVER"]
                ),
                vol.Optional("rs485_log_output_enabled"): cv.boolean,
                vol.Optional("allow_handsfree_mode"): cv.boolean,
                vol.Optional("anonymize_data_in_owner_protocol"): cv.boolean,
            }
        ),
    )

    async def handle_assign_areas_to_lock(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.assign_areas_to_lock(
                call.data["lock_id"], call.data["area_ids"]
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_AREAS_TO_LOCK,
        handle_assign_areas_to_lock,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("area_ids"): [cv.positive_int],
            }
        ),
    )

    async def handle_unassign_areas_from_lock(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.unassign_areas_from_lock(
                call.data["lock_id"], call.data["area_ids"]
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNASSIGN_AREAS_FROM_LOCK,
        handle_unassign_areas_from_lock,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("area_ids"): [cv.positive_int],
            }
        ),
    )

    async def handle_create_sharing_code(call: ServiceCall) -> None:
        await _run(hass, call, lambda e, c: c.create_sharing_code(call.data["lock_id"]))

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SHARING_CODE,
        handle_create_sharing_code,
        schema=BASE_SCHEMA.extend({vol.Required("lock_id"): cv.positive_int}),
    )

    async def handle_remove_sharing_code(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.remove_sharing_code(
                call.data["lock_id"], call.data["sharing_code_id"]
            ),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_SHARING_CODE,
        handle_remove_sharing_code,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("sharing_code_id"): cv.positive_int,
            }
        ),
    )

    async def handle_remove_active_shares(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.remove_lock_active_shares(
                call.data["lock_id"], call.data["aco_ids"]
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ACTIVE_SHARES,
        handle_remove_active_shares,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("lock_id"): cv.positive_int,
                vol.Required("aco_ids"): [cv.string],
            }
        ),
    )

    async def handle_add_shared_lock(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.add_shared_lock(
                call.data["sharing_code"],
                call.data.get("anonymize_data_in_owner_protocol", False),
                call.data.get("alternative_door_name"),
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SHARED_LOCK,
        handle_add_shared_lock,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("sharing_code"): cv.string,
                vol.Optional(
                    "anonymize_data_in_owner_protocol", default=False
                ): cv.boolean,
                vol.Optional("alternative_door_name"): cv.string,
            }
        ),
    )

    # -- holiday calendars --------------------------------------------------

    async def handle_set_holiday_calendar_active(call: ServiceCall) -> None:
        calendar = {
            "id": call.data["holiday_calendar_id"],
            "version": call.data["version"],
            "active": call.data["active"],
        }
        await _run(
            hass,
            call,
            lambda e, c: c.set_holiday_calendar_active(
                call.data["holiday_calendar_id"], calendar
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOLIDAY_CALENDAR_ACTIVE,
        handle_set_holiday_calendar_active,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("holiday_calendar_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Required("active"): cv.boolean,
            }
        ),
    )

    async def handle_add_holiday_calendar_slot(call: ServiceCall) -> None:
        slot = _strip_none(
            {
                "slotName": call.data["slot_name"],
                "validFrom": call.data["valid_from"],
                "validTo": call.data["valid_to"],
                "series": call.data.get("series"),
            }
        )
        await _run(
            hass,
            call,
            lambda e, c: c.add_holiday_calendar_slot(
                call.data["holiday_calendar_id"], slot
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_HOLIDAY_CALENDAR_SLOT,
        handle_add_holiday_calendar_slot,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("holiday_calendar_id"): cv.positive_int,
                vol.Required("slot_name"): cv.string,
                vol.Required("valid_from"): cv.string,
                vol.Required("valid_to"): cv.string,
                vol.Optional("series"): dict,
            }
        ),
    )

    async def handle_update_holiday_calendar_slot(call: ServiceCall) -> None:
        slot = _strip_none(
            {
                "id": call.data["slot_id"],
                "version": call.data["version"],
                "slotName": call.data["slot_name"],
                "validFrom": call.data["valid_from"],
                "validTo": call.data["valid_to"],
                "series": call.data.get("series"),
                "modifyFutureSlots": call.data.get("modify_future_slots", False),
            }
        )
        await _run(
            hass,
            call,
            lambda e, c: c.update_holiday_calendar_slot(
                call.data["holiday_calendar_id"], call.data["slot_id"], slot
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_HOLIDAY_CALENDAR_SLOT,
        handle_update_holiday_calendar_slot,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("holiday_calendar_id"): cv.positive_int,
                vol.Required("slot_id"): cv.positive_int,
                vol.Required("version"): cv.positive_int,
                vol.Required("slot_name"): cv.string,
                vol.Required("valid_from"): cv.string,
                vol.Required("valid_to"): cv.string,
                vol.Optional("series"): dict,
                vol.Optional("modify_future_slots", default=False): cv.boolean,
            }
        ),
    )

    async def handle_delete_holiday_calendar_slot(call: ServiceCall) -> None:
        deletion = {
            "id": call.data["slot_id"],
            "deleteFutureSlots": call.data.get("delete_future_slots", False),
        }
        await _run(
            hass,
            call,
            lambda e, c: c.delete_holiday_calendar_slot(
                call.data["holiday_calendar_id"], call.data["slot_id"], deletion
            ),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_HOLIDAY_CALENDAR_SLOT,
        handle_delete_holiday_calendar_slot,
        schema=BASE_SCHEMA.extend(
            {
                vol.Required("holiday_calendar_id"): cv.positive_int,
                vol.Required("slot_id"): cv.positive_int,
                vol.Optional("delete_future_slots", default=False): cv.boolean,
            }
        ),
    )

    # -- pending phone replacements ---------------------------------------

    async def handle_approve_phone_replacement(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.approve_phone_replacement(call.data["replacement_id"]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPROVE_PHONE_REPLACEMENT,
        handle_approve_phone_replacement,
        schema=BASE_SCHEMA.extend({vol.Required("replacement_id"): cv.positive_int}),
    )

    async def handle_reject_phone_replacement(call: ServiceCall) -> None:
        await _run(
            hass,
            call,
            lambda e, c: c.reject_phone_replacement(call.data["replacement_id"]),
            refresh=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REJECT_PHONE_REPLACEMENT,
        handle_reject_phone_replacement,
        schema=BASE_SCHEMA.extend({vol.Required("replacement_id"): cv.positive_int}),
    )
