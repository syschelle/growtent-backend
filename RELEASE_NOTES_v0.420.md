# GrowTent Backend v0.420 – Plain-text VPD auto status

- **No badge outline:** The VPD tile now displays only the compact **auto** text, without a border, background, chip padding, or rounded corners.
- **Same status colors:** Green means the optional per-tent VPD automation is enabled; orange indicates the most recent sync attempt failed. The label remains hidden when disabled or its status is unavailable. The existing German/English hover explanation stays.
- **No behavior changes:** Status API, tent isolation, 30-second refresh, admin/guest rights, VPD phase/week plans, HMAC, camera, HDR, irrigation, Shelly, backups and schema are unchanged.
- **Verification:** Browser regression checks color-only rendering (including computed background/border), tent switching, both languages, guest view and mobile layout; existing Python, JavaScript, CSP and camera tests remain applicable.
