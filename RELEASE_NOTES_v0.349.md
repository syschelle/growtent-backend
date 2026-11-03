# GrowTent Backend v0.349

## 24-hour ESP Heap diagnostic CSV export

This release makes it easy to share raw ESP memory statistics for troubleshooting intermittent heap warnings and memory fragmentation.

### Dashboard
- Added **Download 24h CSV / 24h CSV herunterladen** beside **ESP Heap history / ESP-Heap Verlauf** for each tent.
- The action is visible to administrators only, on desktop and mobile.
- Downloads an attachment containing all available successful controller poll samples from the preceding 24 hours, in chronological order.

### CSV fields
- `timestamp_utc`: measurement time in UTC (ISO 8601)
- `uptime_seconds`: controller uptime in seconds, useful for identifying reboots
- `free_heap_bytes`: currently available heap
- `min_free_heap_bytes`: lowest free heap since boot
- `largest_free_block_bytes`: biggest contiguous allocatable heap block
- `heap_size_bytes`: reported total heap size
- `largest_over_free_ratio`: contiguous block divided by free heap

### Behavior and security
- Uses existing `tent_state` telemetry retained by the backend (7 days by default); **no new ESP polling**, DB migration, or firmware update required.
- Includes heap samples independently of temperature/VPD filtering.
- Missing or invalid heap metrics remain blank; rows without any usable heap metric are excluded.
- CSV download is restricted to authenticated administrators, including with dashboard authentication disabled.
- If the tent has no data yet, the file contains just the column headers. Polling gaps are preserved as gaps between timestamps, not invented samples.

### Tests
- Added CSV formatting, timestamp, missing-value, production-router, dashboard placement, server-rendered admin/guest HTML, and authorization regression tests.
- Full automated suite: **128 passed**; JavaScript and Python syntax checks: **passed**.
