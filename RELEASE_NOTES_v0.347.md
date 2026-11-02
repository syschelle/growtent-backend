# GrowTent Backend v0.347

## HMAC hint explains the Adjust interface

This maintenance release improves the bilingual HMAC information hint in the Grow Phase card.

### Changed

- The HMAC hint now explains that **Adjust / Anpassen** uses the authenticated controller write interface to change selected Grow values directly on the GrowTent controller.
- The existing HMAC explanation remains: backend and controller share a secret key, write requests are signed, and the controller verifies request integrity and origin.
- The hint continues to clarify that HMAC does not encrypt the HTTP connection.
- No HMAC signing, authorization, Grow Profile, controller write, or transport behavior changed.

### Tests

- Updated dashboard regression coverage for the German and English HMAC hint text.
- Full automated test suite: **111 passed**.
