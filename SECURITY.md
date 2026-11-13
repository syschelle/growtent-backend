# Security — v0.354

Irrigation configuration and manual full-cycle requests use the existing per-tent backend HMAC configuration. The client signs exact serialized bytes and verifies response HMAC, timestamp, request nonce, method/path and HTTP status before trusting success. No unsigned legacy fallback exists. HMAC authenticates and protects integrity; the HTTP LAN channel is not encrypted.

Only administrator write sessions may change plans or request manual cycles. Existing guest/anonymous write restrictions remain in force. A displayed expected revision fences stale plan edits. The ESP retains physical authority and validates clock, Drying, pump/volume settings, Flood, overlap, storage and event capacity.

Manual commands are persisted before transport. Retries retain command_id and expiry with fresh authentication nonces. After an authenticated acceptance, a failed status read is uncertain and cannot justify a replacement identity. Firmware durably claims IDs before execution, retains unexpired claims and rejects unknown expired commands. Backend PostgreSQL advisory locks serialize per-controller UI and poll operations across workers.

Events and notification intent commit atomically before ACK. Unique controller/stream/sequence keys deduplicate ingestion. The outbox retries provider failures independently after ACK. Provider delivery is at-least-once; a crash between provider acceptance and committing delivery can duplicate a push, but cannot trigger watering. Secrets/signatures are never included in event records, API views or new error logs.

Keep the ESP dashboard and PostgreSQL on trusted networks. Protect database backups, which retain the pre-existing HMAC configuration. Configuration-only exports do not preserve the event/notification journal. Firmware power-loss/interlock and real-device integration checks remain open; see TESTING.md.
