# EVVA Airkey for Home Assistant

Custom Home Assistant integration for the [EVVA AirKey Cloud API](https://integration.api.airkey.evva.com/docs/). It exposes the full read surface of your Airkey access control system as sensors, and every write action the API offers as Home Assistant services.

> **Airkey has no remote-unlock endpoint.** AirKey is an offline key/authorization system: access is granted by synchronizing authorizations to a medium (card or phone), not by a cloud relay opening a door. This integration is therefore a monitoring and administration tool, not a remote lock control — there is intentionally no `lock` entity that claims to open anything.

## What it does

**Monitoring** (one shared [DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/), polled on a configurable interval):

- A hub device with sensors for credits, persons, cards, phones, areas, authorizations, blacklist entries, maintenance tasks, holiday calendars, pending phone replacements, access control operators, and the last event — each sensor's full record list is available in its attributes. Cards and phones include whether they're activated (`activated`), which person they're assigned to (`person_id`/`person_name`), and when/where they were last used (`last_used_at`/`last_used_lock_name`). The authorizations list is per (person, lock, medium): area-level authorizations are automatically expanded into one row per lock known to be in that area, so you don't need to separately resolve "access to area X" into individual locks.
- Diagnostic binary sensors for two-factor authentication / four-eyes settings, maintenance-required and pending-phone-replacement alerts.
- A device per lock, with a sensor exposing door name, type, technology, firmware versions, a "removal requested" binary sensor, and who last unlocked it and when (`last_used_at`/`last_used_by_medium_name`, looked up from the lock's protocol history for the last 30 days).
- An `event.*` entity streaming the live audit trail (unlocking, app pairing, authorization synchronization) so you can build automations on real access events. Unlocking events resolve `lock_id`/`lock_name`, `medium_id`/`medium_name` and `person_id`/`person_name` (via the card/phone's assignment), so you can see who unlocked what and with which medium, not just raw IDs.
- A "Refresh data" button, and (only for the free test/integration environment) a "Reset test data" button.

**Administration** — 37 services covering every write endpoint of the API: creating/updating/deleting persons, assigning and managing media (cards/phones), creating and revoking authorizations, sending registration codes and "send-a-key" invites, managing locks/areas/sharing codes, holiday calendars, and pending phone replacements. See **Settings → Devices & services → Airkey** in Home Assistant, or `custom_components/airkey/services.yaml`, for the full list with field descriptions.

## Read-only vs. write access

EVVA issues API keys with different access levels. A free/basic Airkey Cloud Interface key is **read-only**: all sensors work normally, but any service call that would create/update/delete data receives an HTTP 403 from the API. When that happens, the integration raises a clear error instead of failing silently, and creates a repair issue in **Settings → System → Repairs** explaining that the key needs to be upgraded to a production key with write access. Nothing about the free tier prevents monitoring — it just can't drive the write services.

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/reiniertc/airkey` as an "Integration".
2. Install "EVVA Airkey", restart Home Assistant.

### Manual

Copy `custom_components/airkey` into your Home Assistant `custom_components` directory and restart.

## Configuration

Configuration is done entirely through the UI (Settings → Devices & services → Add integration → "EVVA Airkey"):

1. **API key** — create one in the Airkey Online Administration under *Settings → Interfaces → Cloud API*.
2. **Environment**:
   - **Production** — your real Airkey Cloud Interface account (`api.airkey.evva.com`). Requires the paid Cloud Interface activation; write access depends on your license.
   - **Test / integration (free)** — the free `integration.api.airkey.evva.com` environment with predefined test data. Read-only concerns don't apply here since the test environment supports the full API for free, but it never touches your real locks/persons.

Afterwards, use the integration's **Configure** button to change the polling interval (default 720 minutes / 12 hours, minimum 5), the event lookback window used on the very first refresh (default 24 hours), and the lock usage refresh interval (default once a day - see below).

### API request budget

The Airkey Cloud API enforces an (undocumented) daily request quota per account. The main polling cycle costs a fixed number of calls regardless of how many locks you have, but the per-lock "last used" and area-assignment lookups each cost one extra API call per lock, per refresh. To keep the daily total predictable regardless of scan interval, those two are refreshed on their own interval - **once a day by default** - instead of every polling cycle. This once-a-day timestamp is persisted to disk, so a Home Assistant restart doesn't reset it and force an early re-fetch. Use the `airkey.refresh_lock_details` service (or lower the interval in **Configure**) if you want that data sooner than the next scheduled refresh.

The main polling cycle itself costs roughly 15 requests per cycle regardless of scan interval, which is why the default polling interval is a conservative 720 minutes (12 hours, ~30 requests/day) rather than something more "real-time" like 15 minutes (~1400 requests/day). Lower it in **Configure** if your account's quota allows for more frequent updates; note that config entries created before this default changed keep whatever interval they already had, so existing installs need to update it manually if they want the new, more conservative default too.

When a refresh does fail (rate limited or otherwise), entities keep showing the last successfully fetched data instead of going unavailable - a single failed cycle (or a whole day of them, if you're rate limited until midnight UTC) won't blank out your dashboard.

Multiple Airkey accounts (e.g. production and test) can be added side by side as separate config entries.

## Upgrading from 1.x

Version 2.0 is a full rewrite (coordinator-based polling, device registry, options/reauth flow, full API coverage). Existing 1.x config entries are migrated automatically on first start — no need to remove and re-add the integration. The polling interval you had configured is preserved; the environment defaults to "production" (matching 1.x's hardcoded host).

## Development

```bash
pip install -r requirements_test.txt
pytest tests/ -q
ruff check custom_components tests
ruff format --check custom_components tests
```

## License

[MIT](LICENSE)

## Disclaimer

This is an unofficial, community-maintained integration and is not affiliated with or endorsed by EVVA. Use at your own risk.
