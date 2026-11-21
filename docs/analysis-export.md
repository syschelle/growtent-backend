# Historical analysis export: JSON and ZIP

## ZIP download with original + HDR-style camera images (v0.402)

In the Dashboard, **Analyseexport (ZIP)** / **Analysis export (ZIP)** downloads a ZIP for the selected tent and 1h/6h/12h/24h/48h period. It contains the historical JSON file (same schema and values as the prior JSON export) and two renderings of **one current camera frame** when the camera is reachable: byte-identical `camera.jpg` (original) and `camera-hdr.jpg` (HDR-style tone-mapped JPEG). The camera is fetched at the **native resolution of its configured RTSP stream** through go2rtc, without the Dashboard preview's 1280 × 720 limit or artificial upscaling. The original JPEG bytes are stored unchanged whenever they fit. The picture is **not** an archival image from the selected historical period.

The JSON in the ZIP has an additional optional top-level object:

```json
"camera_snapshot": {
  "status": "included",
  "filename": "camera.jpg",
  "width_px": 3840,
  "height_px": 2160,
  "retrieved_at_utc": "2026-11-21T10:10:00Z",
  "hdr": {
    "status": "included",
    "filename": "camera-hdr.jpg",
    "method": "single_frame_tone_mapping",
    "width_px": 3840,
    "height_px": 2160
  }
}
```

`width_px` and `height_px` show the resolution of the JPEG actually saved inside the archive, not a promised camera specification. `retrieved_at_utc` is the time at which the backend **received** the JPEG, not a precise camera exposure timestamp. When the camera is unavailable, `status` and `hdr.status` are `"unavailable"`, their other fields are null, and the ZIP contains `camera-unavailable.txt` (German and English) instead of JPEG files. When the camera is present but HDR-style processing fails, the ZIP still includes `camera.jpg` and a bilingual `camera-hdr-unavailable.txt`; `hdr.status` is `"unavailable"`. **Historical sensor data is still exported unchanged.** Do not treat a missing image as a failed measurement export. The image and RTSP credentials are not stored in the database or mirrored into JSON. Only the JSON remains subject to the original 1 MB export bound. Each image independently respects the 20 MB limit; with both images, an export can contain up to approximately 40 MB of image data. For safety, the camera fetch is capped at 32 MB and a single JPEG in the ZIP at 20 MB. The typical high-resolution photo stays **byte-identical**; only if larger than 20 MB is it recompressed once at JPEG quality 94 (4:4:4, optimized), then, if still necessary, resized proportionally using LANCZOS from the original frame. An exceptionally large HTTP source (>32 MB) is retried at 3840 and 2560 pixels wide via the same internal go2rtc service. Invalid JPEG and unavailable camera responses are handled without breaking the JSON export. The resolution cannot exceed the configured RTSP source stream's actual resolution.

- `GET /api/export/analysis?tent_id=2&range=24h` remains the **original JSON-only endpoint**, unchanged for existing integrations.
- `GET /api/export/analysis.zip?tent_id=2&range=24h` returns `application/zip` and a `.zip` attachment for the Dashboard.
- The archive is produced in memory, with **one** camera frame represented twice; it is not a video or a historical timelapse. The second image is an **HDR-like visualization of a single exposure**, not real HDR fusion: it gently opens shadows and compresses highlights using local luminance, without recovering clipped sensor detail. Original color is preserved as much as possible. HDR output uses high-quality JPEG 94 with 4:4:4 chroma, keeping original dimensions up to 16 MP (including native 4K); exceptionally large frames can be resized proportionally with LANCZOS. Metadata records its actual dimensions and method. No extra camera call or AI enhancement occurs.



## Fullscreen camera display (v0.402)

The camera fullscreen popup ("Vollbild" / "Fullscreen") has two optional view modes, **Original** (default) and **HDR** (single-frame tone mapping, **not** multiple exposure HDR). The main Dashboard's lightweight camera preview remains unchanged. The popup uses the existing `GET /tents/{tent_id}/preview` with an optional `hdr=1` query parameter. This flag is propagated through the modular router and service to the JPEG endpoint and uses the **same** processing function as `camera-hdr.jpg`. On errors the previous image stays visible and the popup reports "Bild nicht verfügbar" / "Image unavailable". No image is persisted by this display route. HDR live refresh is throttled to 5 seconds (normal preview remains 2.5 seconds) to limit CPU usage, and the existing high-resolution still-frame zoom continues to work in either mode. Camera configuration, access checks and all exported files are unchanged.

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

## Exhaust power (v0.394)

Each point includes `metrics.exhaust_watt` (`avg`, `min`, `max`, `n`, unit W), matching `shelly.exhaust.power_w` when present. Canonical `cur.shelly.exhaust.Watt` takes priority; if absent or null, historical `cur.shelly.exhaust.watt` and `shelly.exhaust.watt` are supported in that order. A malformed non-null canonical value is not replaced. Explicit stale or invalid freshness excludes power, while legacy rows without a freshness flag retain valid values. Missing windows report null statistics and `n: 0`, never an inferred zero. These are sampled power readings, not fan speed or airflow. The two paths describe the same data, not separate devices.

## Grow phase and light schedule

`context_first` and `context_last` preserve the first/last observed context with `at` timestamps. Each context contains `phase`, `phase_week`, `phase_day`, `grow_week`, `grow_day`, and `light_schedule.on` / `.off` in normalized `HH:MM` format. Missing fields stay null. Phase codes are the ESP's recorded values (1 vegetative, 2 flowering, 3 drying).

`context_timeline` records the initial context and subsequent observed changes, up to 128 entries. `context_change_count` counts changes, excluding the initial entry; `context_details_omitted` counts entries omitted by the cap. The final context remains available even after this cap.

### Structured VPD-table phase (v0.395)

The top-level `grow_phase` describes the final sample of the selected export, with `grow_phase_observed_at` (UTC). Each point also has its own `grow_phase` from the samples in that bucket, not from current settings. Example:

```json
{
  "phase": "flowering",
  "week": 6,
  "stage": "late",
  "label_de": "Blüte · Woche 6 · spät",
  "label_en": "Flowering · Week 6 · late",
  "reference_vpd_kpa": {"min": 1.2, "max": 1.6}
}
```

Phase codes are `vegetative`, `flowering` and `drying`. Weeks 1–2 are `early`; week 3 onwards is `late`. Reference ranges match the VPD table; these are not controller targets or night-mode assessments. Phase metadata uses stored settings independently of climate-reading freshness. Drying has null stage/reference; missing or invalid week is null, and an unsupported phase is null. No calendar-based or live-state substitution is used.

For homogeneous buckets the phase applies to all sampled records. Empty/unknown buckets have null `grow_phase`. For mixed buckets (including known and unknown phase or week observations), `grow_phase` is null and `grow_phase_counts` contains objects with `grow_phase` and `n`, grouping all observations by phase and week. Counts sum to the bucket's `samples`; the metric aggregates are not separated by phase. Adaptive aggregation retains these counts. The existing context timeline remains unchanged and includes available observation timestamps, subject to its existing detail limit.

Light times are the ESP-stored day-0 schedule, which the firmware exposes as the common daily ON/OFF times. They are device-local clock times, not UTC instants or a reconstructed full weekly Shelly schedule. No day/night classification is guessed. Device IPs and IP-bearing schedule display lines are not exported.

## Size and observation limits

The existing download endpoint adapts window width to stay within 1,000,000 UTF-8 bytes. Minimums, maximums, valid sample counts, state/freshness counts, first/last energy values and total transition counts remain available as windows widen. Details are bounded; `eventDetailsOmitted` counts omitted target/switch details (the legacy humidifier field and its new Shelly entry do not double-count the same omission).

All transition and context timestamps are backend polling observations. Switching between polls cannot be reconstructed. No live status is retroactively assigned to earlier samples.

## HDR appearance update (v0.403)

The optional fullscreen HDR button and `camera-hdr.jpg` now share a stronger, adaptive single-frame tone curve with local clarity. This makes moderate-contrast growtent images visibly easier to inspect. It is still not true multi-exposure HDR, and does not increase native detail. The method metadata is now `single_frame_adaptive_tone_mapping_v2`; `camera.jpg` is untouched.
