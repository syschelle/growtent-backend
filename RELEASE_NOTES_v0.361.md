# GrowTent Backend v0.361

## Changes

- Replace the target-temperature and target-VPD iframe editors with small native dialogs directly in the dashboard.
- Open at their final 280 px width without an opening loader, iframe navigation or height messages.
- Use the current tent's dashboard values immediately; fetch the existing protected profile endpoint once only if no valid cached target is available.
- Keep one input with Save and Cancel, specific headings, ändern/change tile labels and two-decimal current VPD.
- Preserve validation, administrator/readiness checks and the existing backend/HMAC PATCH path. Only controller-verified responses update the dialog's current value.
- Keep pending input on failed writes and ignore stale responses from closed dialogs or different tents.

## Compatibility

- No new backend or ESP endpoint and no firmware update are required.
- The existing Adjust phase/date editor and legacy deep links remain available on their existing path.
- Temperature editing remains in Celsius with 0.5 °C steps; target VPD retains 0.1 kPa steps.

## Validation

Local backend tests pass. Browser fixtures check native opening without target iframe requests, cached values/single-read fallback, exact verified partial PATCH payloads, bounds, errors, cancellation, stale-response/tent guards, DE/EN and mobile placement, plus phase/date compatibility. Existing database, HMAC/security and CodeQL checks remain required. No live controller is contacted by tests.
