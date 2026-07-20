"""Constants for the EVVA Airkey integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "airkey"

# Config / options keys
CONF_ENVIRONMENT: Final = "environment"
CONF_EVENT_LOOKBACK_HOURS: Final = "event_lookback_hours"
CONF_LOCK_DETAILS_INTERVAL_HOURS: Final = "lock_details_interval_hours"

ENV_PRODUCTION: Final = "production"
ENV_TEST: Final = "test"
ENVIRONMENTS: Final = [ENV_PRODUCTION, ENV_TEST]

HOST_BY_ENVIRONMENT: Final = {
    ENV_PRODUCTION: "api.airkey.evva.com",
    ENV_TEST: "integration.api.airkey.evva.com",
}
API_BASE_PATH: Final = "/cloud/v1"

DEFAULT_SCAN_INTERVAL_MINUTES: Final = 720
MIN_SCAN_INTERVAL_MINUTES: Final = 5
DEFAULT_EVENT_LOOKBACK_HOURS: Final = 24

# The per-lock "last used" and "assigned areas" lookups each cost one extra
# API call per lock. Refreshing them on every coordinator cycle (default
# every 15 minutes) can add up fast against the Airkey API's daily request
# quota, so they're refreshed on their own, much longer interval instead -
# use the refresh_lock_details service to force an immediate update.
DEFAULT_LOCK_DETAILS_INTERVAL_HOURS: Final = 24
MIN_LOCK_DETAILS_INTERVAL_HOURS: Final = 1

# How far back to look, per lock, when determining "last used" (lock-protocol
# entries are fetched per lock via a filtered query, so this bound keeps that
# query small and its result reliably complete rather than paging-truncated).
LOCK_PROTOCOL_LOOKBACK_DAYS: Final = 30
# LockProtocolEvent.type values that represent an actual successful unlock
# (as opposed to sync/firmware/admin protocol entries for the same lock).
SUCCESSFUL_UNLOCK_EVENT_TYPES: Final = {
    "UNLOCKING_SUCCESSFUL",
    "UNLOCKING_SUCCESSFUL_VIA_HANDS_FREE",
}

CONFIG_ENTRY_VERSION: Final = 2

MANUFACTURER: Final = "EVVA"

# Event entity event types (EventDetails.type in the API)
EVENT_TYPE_UNLOCKING: Final = "unlocking"
EVENT_TYPE_APP_PAIRED: Final = "app_paired"
EVENT_TYPE_AUTHORIZATION_SYNCHRONIZED: Final = "authorization_synchronized"
EVENT_TYPES: Final = [
    EVENT_TYPE_UNLOCKING,
    EVENT_TYPE_APP_PAIRED,
    EVENT_TYPE_AUTHORIZATION_SYNCHRONIZED,
]
# Maps the API's EventDetails.type enum to our lowercase HA event types
API_EVENT_TYPE_MAP: Final = {
    "UNLOCKING": EVENT_TYPE_UNLOCKING,
    "APP_PAIRED": EVENT_TYPE_APP_PAIRED,
    "AUTHORIZATION_SYNCHRONIZED": EVENT_TYPE_AUTHORIZATION_SYNCHRONIZED,
}

# Repair issue ids
ISSUE_WRITE_ACCESS_DENIED: Final = "write_access_denied"

# Services
SERVICE_REFRESH: Final = "refresh"
SERVICE_REFRESH_LOCK_DETAILS: Final = "refresh_lock_details"
SERVICE_RESET_TEST_DATA: Final = "reset_test_data"

SERVICE_CREATE_PERSON: Final = "create_person"
SERVICE_UPDATE_PERSON: Final = "update_person"
SERVICE_DELETE_PERSON: Final = "delete_person"

SERVICE_CREATE_SIMPLE_AUTHORIZATION: Final = "create_simple_authorization"
SERVICE_CREATE_ADVANCED_AUTHORIZATION: Final = "create_advanced_authorization"
SERVICE_DELETE_AUTHORIZATION: Final = "delete_authorization"

SERVICE_ASSIGN_MEDIUM: Final = "assign_medium"
SERVICE_CANCEL_MEDIUM_ASSIGNMENT: Final = "cancel_medium_assignment"
SERVICE_DEACTIVATE_MEDIUM: Final = "deactivate_medium"
SERVICE_REACTIVATE_MEDIUM: Final = "reactivate_medium"
SERVICE_EMPTY_MEDIUM: Final = "empty_medium"
SERVICE_UPDATE_CARD: Final = "update_card"

SERVICE_ADD_PHONE: Final = "add_phone"
SERVICE_UPDATE_PHONE: Final = "update_phone"
SERVICE_DELETE_PHONE: Final = "delete_phone"
SERVICE_GENERATE_PHONE_PAIRING_CODE: Final = "generate_phone_pairing_code"
SERVICE_RESET_PHONE_PIN: Final = "reset_phone_pin"
SERVICE_SEND_REGISTRATION_CODE_MAIL: Final = "send_registration_code_mail"
SERVICE_SEND_REGISTRATION_CODE_SMS: Final = "send_registration_code_sms"

SERVICE_SEND_A_KEY_MAIL: Final = "send_a_key_mail"
SERVICE_SEND_A_KEY_SMS: Final = "send_a_key_sms"

SERVICE_UPDATE_LOCK: Final = "update_lock"
SERVICE_REMOVE_LOCK: Final = "remove_lock"
SERVICE_ABORT_REMOVE_LOCK: Final = "abort_remove_lock"
SERVICE_UPDATE_LOCK_SETTINGS: Final = "update_lock_settings"
SERVICE_ASSIGN_AREAS_TO_LOCK: Final = "assign_areas_to_lock"
SERVICE_UNASSIGN_AREAS_FROM_LOCK: Final = "unassign_areas_from_lock"
SERVICE_CREATE_SHARING_CODE: Final = "create_sharing_code"
SERVICE_REMOVE_SHARING_CODE: Final = "remove_sharing_code"
SERVICE_REMOVE_ACTIVE_SHARES: Final = "remove_active_shares"
SERVICE_ADD_SHARED_LOCK: Final = "add_shared_lock"

SERVICE_SET_HOLIDAY_CALENDAR_ACTIVE: Final = "set_holiday_calendar_active"
SERVICE_ADD_HOLIDAY_CALENDAR_SLOT: Final = "add_holiday_calendar_slot"
SERVICE_UPDATE_HOLIDAY_CALENDAR_SLOT: Final = "update_holiday_calendar_slot"
SERVICE_DELETE_HOLIDAY_CALENDAR_SLOT: Final = "delete_holiday_calendar_slot"

SERVICE_APPROVE_PHONE_REPLACEMENT: Final = "approve_phone_replacement"
SERVICE_REJECT_PHONE_REPLACEMENT: Final = "reject_phone_replacement"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
