# Historical analysis JSON export

The download uses stored `tent_state.payload` samples in the requested half-open UTC range. It never contacts Shellys or substitutes current settings. Dashboard-only direct readings that were not stored cannot be recovered. Existing `growtent.analysis.v1` climate, target and humidifier fields remain available; v0.385 adds the fields below.

## Shelly measurements in each point

`points[].shelly` contains the supported roles present in that window's source records: `main`, `light`, `humidifier`, `heater`, `heatmat`, `fan`, `exhaust`. Missing roles have no fabricated samples. An empty window has an empty object.

Each role provides:

| Field | Meaning |
|---|---|
| `samples` | Records containing that role's telemetry or configuration |
| `state_first`, `state_last` | First/last observed boolean state, or null |
| `on_samples`, `off_samples`, `unknown_samples` | Counts, not elapsed runtime |
| `fresh_samples`, `stale_samples`, `freshness_unknown_samples` | Explicit true, false or unavailable/invalid freshness flag |
| `power_w` | Average, minimum, maximum and valid sample count (`n`) in watts |
| `energy_wh` | First, last, minimum, maximum and valid count of the recorded energy counter, in Wh |
| `age_ms` | Average, minimum, maximum and valid count of the ESP-reported cache age, in milliseconds |
| `observed_changes`, `transitions` | Total observed boolean state changes and up to eight timestamped details per role/window |

An explicit stale or invalid freshness flag excludes state/power/energy from valid observations. A legacy record without a freshness flag retains its valid measurements but is counted under unknown freshness. Missing, nonfinite and boolean numeric values are not zeros. Unknown state, a missing device record or a sampling gap breaks switch continuity. Power does not imply ON/OFF. PM1 ON can represent the permanently connected output, not a relay operation. Energy counters may reset; no consumption delta or runtime is invented.

## Grow phase and light schedule

`context_first` and `context_last` preserve the first/last observed context with `at` timestamps. Each context contains `phase`, `phase_week`, `phase_day`, `grow_week`, `grow_day`, and `light_schedule.on` / `.off` in normalized `HH:MM` format. Missing fields stay null. Phase codes are the ESP's recorded values (1 vegetative, 2 flowering, 3 drying).

`context_timeline` records the initial context and subsequent observed changes, up to 128 entries. `context_change_count` counts changes, excluding the initial entry; `context_details_omitted` counts entries omitted by the cap. The final context remains available even after this cap.

Light times are the ESP-stored day-0 schedule, which the firmware exposes as the common daily ON/OFF times. They are device-local clock times, not UTC instants or a reconstructed full weekly Shelly schedule. No day/night classification is guessed. Device IPs and IP-bearing schedule display lines are not exported.

## Size and observation limits

The existing download endpoint adapts window width to stay within 1,000,000 UTF-8 bytes. Minimums, maximums, valid sample counts, state/freshness counts, first/last energy values and total transition counts remain available as windows widen. Details are bounded; `eventDetailsOmitted` counts omitted target/switch details (the legacy humidifier field and its new Shelly entry do not double-count the same omission).

All transition and context timestamps are backend polling observations. Switching between polls cannot be reconstructed. No live status is retroactively assigned to earlier samples.
