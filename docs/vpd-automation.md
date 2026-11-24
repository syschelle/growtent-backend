# VPD automation (backend, optional)

**The backend never changes the grow phase.** Switching between vegetative, flowering and drying is only possible via the existing ESP/operator workflow. The automation observes the reported phase and adjusts only `targetVPD` when explicitly enabled.

The ESP remains the sole actuator and supplies the **current** `settings.grow.currentPhase` and `settings.grow.currentPhaseWeek` in `/api/state`. GrowTent Backend never guesses phase/week from the database ID or historical export. Phase 1 is vegetative, phase 2 flowering and phase 3 drying. Drying uses a single adjustable phase target, **0.90 kPa by default**, when the automation is enabled; it does not use a weekly schedule or require a reported drying week. The normal read-only `vpd-table.js` reference chart remains unchanged.

## Setup

In **Setup → Tents**, choose **VPD-Automatik / VPD automation** for the selected tent. Enter target VPD values in kPa for successive weeks of vegetative growth and flowering; the last value is held indefinitely for subsequent weeks **within the same phase**. When either vegetative or flowering growth lasts beyond its configured entries, it remains in that same ESP-reported phase and holds the final phase-specific value without redundant HMAC writes. A long vegetative phase never advances into flowering; a long flowering phase never advances into drying. Drying has one phase-wide value (default **0.90 kPa**) and no weekly schedule. Values must be 0.50–3.50 kPa (up to two decimals). **Enabled** defaults to false. Enabling requires Backend Write enabled, a controller URL and an HMAC secret for that tent.

The supplied *editable example* schedule is:

| Phase | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vegetative | .60 | .70 | .90 | 1.00 | 1.10 | 1.15 | 1.15 | 1.15 | 1.15 | 1.15 |
| Flowering | 1.00 | 1.10 | 1.25 | 1.30 | 1.35 | 1.40 | 1.40 | 1.35 | 1.30 | 1.30 |
| Drying | **0.90** | same fixed target for the whole phase | — | — | — | — | — | — | — | — |

These are configurable controller starting values, **not plant-specific instructions**. During drying, the target is a device setting for the drying environment, **not a physiological VPD reference for a living plant**. Review temperature, relative humidity and moisture conditions before opting in.

## Behavior

- The next successful controller poll after enabling/reconfiguring attempts to set the target for the reported phase/week (unless already at that value). Drying requires only `currentPhase=3`, not a valid `currentPhaseWeek`; it is represented internally as phase 3/week 1 for one-time change tracking.
- After success, only a **new configured week in the same phase**, an **actual ESP-reported phase change**, or a **changed plan** triggers another write. Weeks beyond the last configured entry count as the **same final plan week**, even if the ESP reports week 7, 8, etc.; the final target holds, and manual changes are not overwritten by extra weeks. During drying, changing the reported week never triggers further writes. The automation does not run a continuous controller loop and never issues a phase-change command.
- Writes are limited to `targetVPD` via the existing HMAC write path; no temperature/phase/lighting changes.
- Claiming and last-success metadata persist in PostgreSQL and are scoped by `tent_id`; failed writes retry no sooner than 30 minutes later.
- The last-success week shown in the UI is the **applied plan slot** (e.g. week 6 for a six-week vegetative plan, even if the ESP is currently in week 9). This does not override the ESP's actual week.
- Editing the full plan is admin-only: `GET/PUT /tents/{tent_id}/vpd-auto`. The Setup UI shows the last successfully applied phase/week/target. The small, read-only `GET /tents/{tent_id}/vpd-auto/status` returns only `tentId`, `enabled` and `lastSyncFailed` to authenticated users (including guests); it never returns targets or secrets.
- In the Dashboard VPD tile, a small **auto** label appears in **green** when automatic control is enabled and in **orange** when the latest sync attempt is marked failed. Disabled automation shows no label. Green means *enabled*, not necessarily that a new write has succeeded. On an unavailable status endpoint the indicator stays hidden. The label updates at the Dashboard refresh interval (30 seconds) and follows the selected tent. Hover/focus shows a localized explanation; the icon is deliberately short in the UI.
- Old backups without VPD automation plans import with automation disabled. Plans stored by v0.417 without a `drying` key remain usable and receive the default 0.90 kPa on load. New encrypted backups include per-tent schedules including drying, not transient claim state.

No ESP firmware update is necessary if its backend HMAC grow-profile write API already supports `targetVPD`. No historical analysis measurements are modified. Verify the actual target in Dashboard after the first change, and disable the switch immediately if values are unsuitable.
