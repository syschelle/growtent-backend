# Security — v0.356

Irrigation configuration and manual full-cycle requests use the existing per-tent backend HMAC configuration. The client signs exact serialized bytes and verifies response HMAC, timestamp, request nonce, method/path and HTTP status before trusting success. No unsigned legacy fallback exists. HMAC authenticates and protects integrity; the HTTP LAN channel is not encrypted.

Only administrator write sessions may change plans or request manual cycles. Existing guest/anonymous write restrictions remain in force. A displayed expected revision fences stale plan edits. The ESP retains physical authority and validates clock, Drying, pump/volume settings, Flood, overlap, storage and event capacity.

Manual commands are persisted before transport. Retries retain command_id and expiry with fresh authentication nonces. After an authenticated acceptance, a failed status read is uncertain and cannot justify a replacement identity. Firmware durably claims IDs before execution, retains unexpired claims and rejects unknown expired commands. Backend PostgreSQL advisory locks serialize per-controller UI and poll operations across workers.

Events and notification intent commit atomically before ACK. Unique controller/stream/sequence keys deduplicate ingestion. The outbox retries provider failures independently after ACK. Provider delivery is at-least-once; a crash between provider acceptance and committing delivery can duplicate a push, but cannot trigger watering. Secrets/signatures are never included in event records, API views or new error logs.

Keep the ESP dashboard and PostgreSQL on trusted networks. Protect database backups, which retain the pre-existing HMAC configuration. Configuration-only exports do not preserve the event/notification journal. Firmware power-loss/interlock and real-device integration checks remain open; see TESTING.md.

## v0.356 diagnostics

Known unsigned controller rejection codes may be displayed only as explicitly unverified diagnostics. They never authenticate a success or authorize a legacy fallback. An ambiguous POST retains its command identity. Event/ACK errors do not revoke an independently signed plan confirmation; writes still require a fresh signed read and matching revision. Old or genuinely failed plan snapshots remain read-only.

## v0.358 target tile editors

New tile controls are rendered only for administrator sessions and use the existing protected Grow Profile page and PATCH endpoint. Existing source-IP/HMAC/time/nonce checks and confirmation logic remain authoritative. Editor sections are allowlisted; scope limits client payloads but is not a new authorization boundary. No controller secrets enter HTML or browser requests. Guest/offline/unconfigured visibility and scoped payload isolation are regression tested with synthetic fixtures.

## v0.359 labels

Only the visible target-button labels change; specific dialog names, permission/readiness gates, scoped payloads and authenticated write paths remain unchanged.

## v0.360 modal readiness

Dialog size/readiness messages still require the expected same origin and iframe source and now also match the active navigation view identifier. This identifier prevents stale UI updates and is not an authentication credential. Administrator and HMAC write enforcement are unchanged. Loading can be dismissed, and load failures do not authorize writes.

## v0.361 native target dialogs

Target forms use the same administrator-protected profile API and backend/HMAC write service. Cached numeric values are bound to a tent and taken only from its actual latest payload, not another tent’s fallback. Submission rechecks readiness/tent identity; stale responses cannot modify a new dialog. Only verified responses with the requested numeric value are displayed as successful. No secrets or arbitrary HTML are added to the dialog. Unknown values remain unknown until a protected read succeeds.

## v0.362 VPD precision

Client VPD editing uses hundredths within the existing allowed range. Formatting alone does not create a pending write, invalid third-decimal drafts are not silently submitted, and payloads remain numeric through the existing protected/HMAC path. No access boundaries or endpoints change.

## v0.363 native phase/date dialog

Moving Adjust into the Grow Phase tile and replacing its iframe does not change authorization. The native dialog is rendered only for administrator sessions and requires configured writes plus an online/OK controller. It sends only modified phase/date fields through the existing protected endpoint. Existing dates require explicit Delete; deletion sends JSON null. Success requires verified controller state matching every requested change. Failed reads, unverified responses and stale/tent-switched dialogs cannot enable or confirm writes. No HMAC secrets are sent to the browser.

## v0.364 ESP VPD channel integrity

Only the ESP current VPD channel supplies live/control/history VPD. Missing, nonfinite, boolean, negative and explicitly invalid/stale climate inputs cannot be replaced by a calculation, raw channel or cached prior VPD. Existing backend exhaust control performs no network action without a valid control VPD. New normalization copies payloads and preserves stored history; it does not establish cryptographic measurement provenance. No authentication/HMAC, firmware, target or hysteresis change is introduced.

## v0.365 chart presentation

Climate axis suggestions only affect presentation. Data, exports, control decisions and authentication are unchanged; larger excursions remain visible.

## v0.366 chart preferences

Chart ranges are non-sensitive browser-local presentation settings. Stored JSON is type/range validated, never inserted as HTML and cannot alter controller configuration or measured data. No new write API or authorization behavior is introduced.

## v0.367 history target fields

JSON history projections add only the recorded climate targets, normalized to finite numbers or null. No secrets, extra controller requests or new authorization paths are introduced. Stored measurements and settings are not modified.

## v0.368 analysis download

The new read-only analysis export follows existing dashboard history authentication. It accepts only fixed 1–48h ranges, uses bound SQL parameters, emits a fixed metric/target allowlist and never includes stored payloads, IPs, tokens or HMAC secrets. Attachment filenames use numeric tent IDs and a server timestamp. Responses are no-store and bounded to 1,000,000 bytes by adapting window sizes. No writes or ESP requests are performed.

## v0.369 export wording

Only the explanatory dialog text changes. The backend still downloads a file locally and does not send data to ChatGPT or any other AI service. Existing export access and file-content safeguards remain unchanged.

## v0.370 VPD reference view

The table is a read-only browser projection of existing authorized latest-state responses. It adds no data/write endpoint, network poll or control decision. Only numeric allowlisted fields are read; table content uses DOM textContent. Invalid/stale timestamps and climate flags remove the live marker. Calculated cells cannot overwrite the central ESP regulation VPD.

## v0.371 VPD tile layout

Only action placement changes. Existing read-only table behavior and administrator/readiness restrictions for target edits are unchanged.

## v0.372 phase-aware references

Phase/week references and stage split preferences are display-only. Phase data comes from the current authorized ESP snapshot; unknown/stale data selects no phase band. Per-tent localStorage values are integer/range validated and are not controller settings. No target writes, phase changes or new network endpoints are introduced.

## v0.373 table colours

Only reference-table colour classification changes. Controller readings, authorization, HMAC writes and physical control remain unchanged.

## v0.374 hint text

German display copy only; security and controller behaviour are unchanged.

## v0.375 VPD tile assessment

The tile reuses the read-only phase/week reference with compact inline DE/EN text. Stale data and drying do not claim an in-range value. ESP regulation and write security remain unchanged. Browser coverage checks closed-dialog updates and stale expiry.

## v0.376 guest VPD table

Guest table open/close and browser-local week mapping controls are exempt from guest pointer blocking, matching the existing JavaScript allowlist. Controller write restrictions remain unchanged. Browser regressions cover guest table access and blocked VPD target editing.
