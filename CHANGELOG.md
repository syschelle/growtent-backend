# Changelog

## v0.182

### Chart.js reliability fix
Removed external CDN dependency for charts.

### Changes
- Added local static asset: `api/static/chart.umd.js`.
- Mounted `/static` in FastAPI.
- Dashboard now loads Chart.js from `/static/chart.umd.js`.

### Effect
- Charts work in restricted/offline environments where jsDelivr is blocked.


## v0.181

### Chart order tweak (local)
Moved DS18B20 history chart above Alpha history chart in dashboard order.


## v0.180

### Chart rendering (local)
Removed visual line smoothing for Alpha History and Total Consumption charts.

### Changes
- Alpha chart datasets now use `tension: 0`.
- Total consumption chart (`mainWChart`) now uses `tension: 0`.
- Data values are unchanged; only curve interpolation is removed.


## v0.179

### Deployment note (docs)
Added guidance for running updates directly from the GitHub repository.

### Recommended compose options
- Prefer registry image updates when available (`image:` + `pull_policy: always`).
- Alternative: build directly from GitHub source (`build.context: https://github.com/syschelle/growtent-backend.git#main:api`).
- Typical update commands:
  - `docker compose pull api && docker compose up -d api` (image flow)
  - `docker compose build --no-cache api && docker compose up -d api` (git-build flow)


## v0.178

### Warmup counter wording (local)
Added translated unit text after counter value in history warmup overlay.

### Changes
- DE: `(<X> Messpunkt(e) verbleibend)`
- EN: `(<X> data point(s) remaining)`


## v0.177

### History warmup counter (local)
Warmup overlay now includes remaining point count until charts are considered built.

### Changes
- During warmup (`points < 30`) overlay shows remaining counter:
  - DE: `Historie wird noch aufgebaut… (noch X)`
  - EN: `History is still building up… (X remaining)`


## v0.176

### History warmup message placement (local)
Moved "History is still building up…" from top status area into each history chart card center as red overlay text.

### Changes
- Added centered per-chart overlay placeholders for all history cards.
- Added `setHistoryOverlays(message)` helper.
- During warmup (`points < 30`) show overlay text in chart centers.
- Removed warmup text from top status line.


## v0.175

### Startup responsiveness fix (local)
Initial dashboard render no longer waits on slow Shelly direct-all calls.

### Changes
- `loadLatest()` now fetches `/shelly/direct-all` in background (non-blocking).
- Added 1200ms abort timeout for direct-all fetch.
- Prevents delayed first paint of stream/value cards on page refresh.


## v0.174

### Poll continuity / online state fix (local)
When controller temporarily delivers null sensor values, backend now keeps continuity from last known sample instead of dropping the poll.

### Changes
- Added `_get_last_payload(tent_id)` helper.
- `save_state()` no longer discards incomplete samples immediately.
- For missing raw/smoothed channels, backend backfills from last stored payload.
- New poll samples are persisted, keeping `captured_at` fresh and preventing false offline state.


## v0.173

### Raw/smoothed key alignment (local)
Aligned backend and UI to controller key semantics:
- `sensors.cur.temperatureC` / `sensors.cur.humidityPct` = smoothed/current
- `sensors.cur.temperatureRawC` / `sensors.cur.humidityRawPct` = raw

### Changes
- save/history/export now prefer raw keys from `sensors.cur.*Raw*`.
- Raw fallback compatibility kept for legacy `sensors.raw.*`.
- UI raw value cards now prefer `sensors.cur.temperatureRawC` and `sensors.cur.humidityRawPct`.


## Permanente Systembeschreibung

### Projektziel
CanopyOps ist ein dockerisiertes Multi-Tent-Backend für GrowTent-Controller mit Fokus auf stabilen Betrieb, klare Bedienung und schnelle Diagnose.
Die Plattform bündelt mehrere Zelte in einer Oberfläche und kombiniert Live-Status, Historie, direkte Shelly-Steuerung, Kamera-Previews, Setup-Flow und Authentifizierung.

Aktueller Schwerpunkt:
- direkte Shelly-Anbindung für **alle relevanten Gerätewerte** (Status/Watt/Wh) statt verzögertem State-only-Read
- verlässliche Energiehistorie inkl. Ausreißer-Glättung für Charts/Export
- mehrsprachige, mobilefreundliche UI (DE/EN)
- 2FA-fähiger Zugang mit sauberem Setup-/Login-Flow
- zeltbezogene Bewässerungsplanung + min.-VPD-Überwachung (8x-spezifisch)

### Project Goal (EN)
CanopyOps is a Dockerized multi-tent backend for GrowTent controllers, focused on stable operation, clear UX, and fast diagnostics.
It brings multiple tents into one interface and combines live status, history, direct Shelly control, camera previews, setup flow, and authentication.

Current focus:
- direct Shelly integration for **all relevant device values** (state/Watt/Wh) instead of delayed state-only reads
- reliable energy history with spike filtering for charts and exports
- multilingual, mobile-friendly UI (DE/EN)
- 2FA-capable access with clean setup/login flow
- tent-specific irrigation planning + min. VPD monitoring (8x-specific)

### Technische Umsetzung
- FastAPI-App modularisiert:
  - `api/main.py` (App-Initialisierung)
  - `api/routes/*` (Endpoint-Gruppen)
  - `api/services/*` (Business-Logik)
  - `api/db/*` (DB-Zugriffe/Queries)
  - `api/models/*`, `api/core/*`
- Persistenz über PostgreSQL (Tent-Metadaten, Verlaufsdaten, Planungsdaten)
- Polling der Controller über `/api/state` (mit no-cache-Strategie im UI)
- Direkter Shelly-Zugriff (Gen1/Gen2) mit Auth-Strategie (Basic/Digest/Fallback) für aktuelle Live-Werte
- RTSP/Preview-Einbindung über go2rtc
- Deployment über Docker Compose
- UI mit DE/EN, Theme, responsivem Layout und App-Shell-Navigation

### Kernfunktionen
- Multi-Tent Dashboard mit Live-Werten, Historiencharts und relativen Update-Zeiten
- Shelly-Gerätekarten inkl. Toggle, ON/OFF-Zeitplananzeige und Energie-/Kostenwerten
- Direkter Sammel-Read für Shellys (`direct-all`) zur UI-Aktualisierung
- Gesamtverbrauchshistorie aus Shelly-Main-Daten statt ESP32-Fallback
- CSV-Export historischer Sensorwerte (`/api/export`) inkl. raw + smoothed Spalten
- Kamera-Preview je aktivem Zelt (bandbreitenschonend)
- Setup für Zelte, Auth/2FA, Sprache/Theme/Einheiten
- 8x-spezifische Funktionen (Tank, Pumpen/Relais, Bewässerungsplan, min. VPD Überwachung)

### Systemanforderungen
#### Runtime
- Docker Engine + Docker Compose (Plugin)
- Netzwerkzugriff vom API-Container auf:
  - ESP32 Controller-APIs (`/api/state`, Steuer-Endpunkte)
  - Shelly-Geräte (HTTP/RPC, Gen1/Gen2)
  - RTSP-Quelle(n) für go2rtc

#### Firmware-Voraussetzung (ESP32 Relay Boards)
- Das Backend setzt für ESP32 Relay Boards das Repository `https://github.com/syschelle/GrowTent` voraus.
- Erwartet werden die dort bereitgestellten API-Strukturen/Keys (u. a. Status-/Settings-Payload, Shelly-Mapping, Schalt-/Action-Endpunkte).
- Ohne kompatible Firmware aus diesem Repo sind Teile der Dashboard-Logik (insb. Relais-/Shelly-/Planungsfunktionen) nur eingeschränkt nutzbar.

#### Ports (Standard)
- `8088/tcp` → CanopyOps API/UI (`gt_api`)
- `1984/tcp` → go2rtc Web/API (`gt_go2rtc`)
- `8554/tcp` → RTSP (`gt_go2rtc`)
- PostgreSQL intern über Compose-Netz (`gt_db`)

#### Software/Stack
- Python 3.12 (Container-Base)
- FastAPI + Uvicorn
- PostgreSQL
- go2rtc

#### Persistenz & Betrieb
- DB-Retention für Historie standardmäßig `RETENTION_DAYS=7`
- Zeitangaben in UI relativ („vor/ago …“) plus direkte Statuszeitstempel
- Changelog-/Versionspflege bei jeder relevanten Änderung

### Laufende Dienste
- `gt_api` (FastAPI) auf Port `8088`
- `gt_db` (PostgreSQL)
- `gt_go2rtc` auf Ports `1984` und `8554`

---

## v0.171

### Climate pipeline simplification (local)
Backend Adaptive/EMA re-smoothing removed from persistence/history/export path.

### Changes
- `save_state()` now trusts controller channels as source of truth:
  - raw from `sensors.raw.*` (fallback `sensors.cur.*`)
  - smoothed from `sensors.smoothed.*` (fallback `sensors.cur.*`, then raw)
- `/tents/{tent_id}/history` no longer recomputes EMA smoothed values.
- `/api/export` no longer recomputes EMA smoothed values.
- Existing raw/smoothed/alpha fields remain for compatibility.

## v0.172

### Climate channel semantics fix (local)
Aligned channel usage with controller semantics: `raw` is real sensor data, `cur` is smoothed.

### Changes
- Removed fallback from `sensors.raw.*` to `sensors.cur.*` in save/history/export paths.
- Backend now treats missing raw as missing raw (no implicit substitution with smoothed values).
- Smoothed fallback remains `sensors.smoothed.* -> sensors.cur.*`.

## v0.170 (rollback)

### Rollback
Rollback auf v0.170-Verhalten nach Performance-/UX-Regressionen.

### Zurückgenommen
- Aggressiver Fast/Full-Refresh-Scheduler
- Startup-LocalStorage-Sofortcache für Latest-Werte
- Shelly-Direct-Toggle für alle Geräte (zurück auf bewährtes Verhalten: Main direkt, andere via Controller-Action)

## v0.177

### Performance
Dashboard-Refresh entlastet (spürbar weniger Trägheit).

### Änderungen
- `refresh()` kann jetzt `full` oder `fast`:
  - **fast**: nur `loadLatest()`
  - **full**: `loadTentNav()` + `loadLatest()` + `loadHistory()`
- Intervall angepasst:
  - alle 30s fast refresh
  - full refresh nur alle 2 Minuten
- Bei Sprach-/Einheitenwechsel weiterhin full refresh.

### Effekt
- Weniger schwere Chart-/History-Rebuilds
- schnellere UI-Reaktion im Alltag

## v0.176

### UX / Startup
Letzte bekannte Werte werden jetzt sofort beim Laden angezeigt (ohne auf `/latest` warten zu müssen).

### Änderungen
- Browser-Cache pro Zelt eingeführt (`localStorage`):
  - Key: `gt_latest_<tent_id>`
- Beim Start von `loadLatest()`:
  - sofortige Vorbelegung aus Cache (`renderFastLatest(...)`)
  - anschließend normaler Live-Fetch
- Bei gültigen neuen Werten wird der Cache aktualisiert.

### Effekt
- Kein leeres Dashboard in den ersten Sekunden bei verzögerter Quelle.
- Nutzer sieht unmittelbar den letzten bekannten Zustand.

## v0.175

### Resilience
Bei verzögerter/ausfallender Quelle zeigt Dashboard initial weiterhin letzte bekannte Werte.

### Änderungen
- Frontend-Fallback in `loadLatest()`:
  - merkt sich `lastGoodLatestPayload` + `lastGoodCapturedAt`
  - wenn `/latest` leer kommt, werden die letzten gültigen Werte weiter angezeigt
- Statushinweis bei alten Daten (>15 min):
  - DE: `Zeige letzte bekannte Werte (Quelle verzögert/nicht erreichbar).`
  - EN: `Showing last known values (source delayed/unreachable).`

## v0.174

### Shelly Direct Mode (all devices)
Direktes Auslesen/Ansprechen für alle Shelly-Geräte vereinheitlicht.

### Änderungen
- Toggle für alle unterstützten Shelly-Keys jetzt direkt über Shelly-UI/API:
  - `main`, `light`, `humidifier`, `heater`, `fan`, `exhaust`
- Neue interne Direkt-Toggle-Funktion:
  - `_toggle_shelly_direct_for_key(...)`
- Fallback-Proxy für diese Geräte entfernt (direkter Pfad ist Standard).
- Modul-Router ergänzt:
  - `GET /tents/{tent_id}/shelly/direct-all` in `api/routes/tents.py`
  - Service-Delegation in `api/services/tent_service.py`

## v0.173

### Setup Layout (grouped)
Hauptgruppierung nach Wunsch umgesetzt:
- links: **Darstellung**
- Mitte links: **Zugriff** (Adminmodus, 2FA, Backup/Restore, Gastmodus untereinander)
- Mitte rechts: **Statusmeldungen** (Pushover)
- rechts: **Backup**
- darunter: **Zelte**

### Details
- 4-Spalten-Desktop-Layout mit festen Grid-Positionen.
- Zugriff-Teilbereich vertikal gruppiert in einer Spalte.
- Rubriken-Titel angepasst (DE/EN): `Statusmeldungen`, `Backup`, `Zelte`.
- Tablet/Mobile behalten responsive Fallback (2/1 Spalten).

## v0.172

### Setup Layout
Gewünschte Reihenfolge umgesetzt:
- Darstellung, Zugriff, Statusmeldungen, Backup **nebeneinander**
- darunter **Zelte**

### Änderungen
- Setup-Karten mit festen Grid-Positionen versehen:
  - `appearanceCard`, `accessCard`, `pushoverCard`, `backupCard` in einer Zeile
  - `setupTentsCard` über volle Breite in der nächsten Zeile
- Weitere Karten (Gastmodus, 2FA, Recovery) folgen darunter.
- Responsive Fallback bleibt aktiv (Tablet/Mobile automatisch 2/1 Spalten).

## v0.171

### Setup UI Refresh
Setup-Seite neu strukturiert und aufgeräumt (Rubriken + eigene Pushover-Kachel).

### Änderungen
- Neue Rubriken/Section-Titel:
  - Appearance
  - Access
  - Security & Backup
  - Devices & Tents
- Pushover ist jetzt als **eigene Kachel** ausgelagert:
  - Titel: `Pushover status notifications` / `Pushover-Statusmeldungen`
  - Felder: App Token, User Key, Device
- Kartenstil verbessert:
  - klarere Card-Borders, Schatten, konsistentere Abstände
- i18n für neue Rubriken/Titel ergänzt (DE/EN).

## v0.170

### Setup / Pushover
Pushover-Werte jetzt direkt im Setup eingabbar (nicht nur Device).

### Änderungen
- Adminmodus erweitert um Felder:
  - `Pushover app token`
  - `Pushover user key`
  - `Pushover device (optional)`
- `/config/auth` liest/speichert jetzt alle drei Werte.
- DB-Migration ergänzt:
  - `app_auth_config.pushover_app_token`
  - `app_auth_config.pushover_user_key`
- Pushover-Sendelogik nutzt nun Priorität:
  1) Setup/DB Token+User
  2) ENV Token+User (`PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY`)
- Backup/Restore enthält nun zusätzlich:
  - `pushover_app_token`
  - `pushover_user_key`
  - `pushover_device`

## v0.169

### Setup / Pushover
Pushover-Device jetzt im Setup konfigurierbar (persistiert in DB).

### Änderungen
- Setup (Adminmodus): neues Feld
  - EN: `Pushover device (optional)`
  - DE: `Pushover-Gerät (optional)`
- `/config/auth` erweitert:
  - liest/schreibt `pushover_device`
- DB-Migration:
  - `app_auth_config.pushover_device` hinzugefügt
- Pushover-Versand nutzt Device-Reihenfolge:
  1) API payload `device`
  2) Setup/DB `pushover_device`
  3) ENV `PUSHOVER_DEVICE`
- Backup/Restore erweitert um `pushover_device`.

## v0.168

### Pushover
Device-Ziel ist jetzt konfigurierbar.

### Änderungen
- Neue ENV-Option:
  - `PUSHOVER_DEVICE`
- `POST /notify/status` unterstützt optional:
  - `device` im JSON-Body
- Versandlogik nutzt Priorität:
  1) `payload.device`
  2) `PUSHOVER_DEVICE`
  3) kein Device-Feld (alle Geräte)

## v0.167

### Feature
Pushover-Integration für Statusnachrichten im Backend.

### Änderungen
- Neue ENV-Konfiguration:
  - `PUSHOVER_APP_TOKEN`
  - `PUSHOVER_USER_KEY`
- Neues API-Endpoint:
  - `POST /notify/status`
  - Body: `{ "title": "...", "message": "...", "priority": 0 }`
- Poller-Statusmeldungen integriert (Transition-basiert, nicht bei jedem Poll):
  - Offline-Übergang: `CanopyOps: tent offline`
  - Recovery-Übergang: `CanopyOps: tent online`
- Modul-Router verdrahtet (`api/routes/system.py`), damit Endpoint im `main.py`-Stack verfügbar ist.

## v0.166

### Setup UI
2FA-Recovery-Sektion in „Backup und Restore“ umbenannt (inkl. Übersetzung).

### Änderungen
- Titel geändert:
  - EN: `Backup and Restore`
  - DE: `Backup und Restore`
- Save-Button in der Sektion angepasst:
  - EN: `Save backup/restore`
  - DE: `Backup/Restore speichern`
- i18n-Keys ergänzt und in `applySetupI18n()` verdrahtet.

## v0.165

### Setup UI
Admin- und Gast-Zugriff in getrennte Kacheln aufgeteilt + Titel angepasst.

### Änderungen
- Titel `Zugriff` umbenannt zu `Adminmodus` (EN: `Admin mode`).
- Setup-Layout aufgeteilt in zwei separate Karten:
  - **Adminmodus** (Auth aktivieren, Username, Passwort, Generator, Save)
  - **Gastmodus** (read-only, Username, Passwort, Ablaufzeit, Generator, Save guest)
- Funktionalität bleibt identisch, nur klarere Trennung in der Oberfläche.

## v0.164

### Setup UI
Sichtbarkeit für Guest-Passwort ergänzt.

### Änderungen
- Neues Toggle im Guest-Bereich:
  - `showGuestPassword` + Label `Show password`
- Verhalten wie beim Admin-Passwort:
  - Checkbox an → `type=text`
  - Checkbox aus → `type=password`
- i18n-Anbindung für Guest-Label ergänzt.

## v0.163

### Setup UI
Passwortgenerator im Access-Setup für beide Passwortfelder verfügbar.

### Änderungen
- Neuer Button bei Guest-Login:
  - `Generate password` (`genGuestPassBtn`)
- Bestehender Generator für Admin-Password refactored auf gemeinsame Funktion:
  - `generateStrongPassword(...)`
- i18n-Anbindung ergänzt (Generator-Label auch für Guest-Button).
- Generierte Passwörter werden ins jeweilige Feld eingetragen und können direkt mit `Save`/`Save guest` gespeichert werden.

## v0.162

### UI
Buttons für kleine Geräte ausgeblendet (Phone/Tablet).

### Änderung
- Auf Viewports `<= 1024px` werden folgende Buttons im Dashboard versteckt:
  - `CSV exportieren`
  - `ESP öffnen`
  - `Stats öffnen`
- Umsetzung per responsive CSS mit `display:none !important`.

## v0.161

### Fix
`/app?page=dashboard` konnte mit Internal Server Error enden.

### Ursache
`legacy.dashboard_page(...)` erwartet seit v0.160 ein `Request`-Argument (wegen Redirect-Logik),
aber der modulare Router (`api/routes/system.py`) hat `dashboard_page()` weiterhin ohne Request delegiert.

### Änderung
- `api/routes/system.py` angepasst:
  - `def dashboard_page(request: Request):`
  - `return legacy.dashboard_page(request)`
- Version auf `v0.161` erhöht.

## v0.160

### UX
Landing/Navigation auf App-Shell vereinheitlicht.

### Änderungen
- `/` leitet jetzt direkt auf `/app?page=dashboard` weiter.
- `/dashboard` leitet ohne `embed=1` ebenfalls auf `/app?page=dashboard` weiter.
- Ergebnis: kein direktes Standalone-Dashboard als Landingpage; Einstieg immer über App-Shell.
- Das zuletzt gewählte Zelt bleibt erhalten (wie bisher über `gt_tent_id` im Frontend).

## v0.159

### Fix
Regex-Escape-Warnungen im eingebetteten JS vollständig bereinigt.

### Änderung
- Zusätzlich zu `\\s` jetzt auch `\\d` im Python-String escaped,
  damit Python keine `SyntaxWarning: invalid escape sequence` mehr ausgibt.
- Version auf `v0.159` erhöht.

## v0.158

### Fix
Build-Warnung entfernt: `SyntaxWarning: invalid escape sequence '\s'`.

### Ursache
In eingebettetem JS-RegEx innerhalb des Python-Strings stand `\s`, was von Python als ungültige Escape-Sequenz gewarnt wurde.

### Änderung
- JS-RegEx im HTML-String auf `\\s` im Python-Quelltext escaped,
  sodass im Browser korrekt `\s` ankommt.
- Version auf `v0.158` erhöht.

## v0.157

### Verbesserung
Preview-Auflösung erhöht (Dashboard + Vollbild), renderbar über API-Proxy.

### Änderungen
- `GET /tents/{tent_id}/preview` unterstützt jetzt Query-Parameter:
  - `w` (Breite), `h` (Höhe), `q` (JPEG-Qualität)
  - Defaults: `w=1280`, `h=720`, `q=85`
- Frontend nutzt jetzt getrennte Profile:
  - Inline-Preview: `1280x720`, `q=80`
  - Vollbild-Preview: `1920x1080`, `q=90`
- Weiterhin über gleiche Domain (`/tents/{id}/preview`) ohne externen go2rtc-Port.

## v0.156

### Fix
`/tents/{id}/preview` war in der modularen FastAPI-Router-Schicht nicht registriert (`main.py` läuft über `routes/*`).

### Ursache
Preview-Endpoint wurde nur in `api/app.py` (legacy) ergänzt, aber nicht in `api/routes/tents.py`/`api/services/tent_service.py` verdrahtet.
Dadurch kam auf laufenden Systemen: `{"detail":"Not Found"}`.

### Änderungen
- `api/routes/tents.py`:
  - neuer Route-Eintrag `GET /tents/{tent_id}/preview`
- `api/services/tent_service.py`:
  - neue Methode `preview(...)` delegiert an `legacy.tent_preview(...)`
- Version auf `v0.156` erhöht.

## v0.155

### Fix
Preview-Proxy robuster gemacht (kein hartes Ausblenden bei fehlendem RTSP-Feld).

### Änderungen
- `latest_state` liefert `preview_url` jetzt immer als `/tents/{tent_id}/preview`.
- Preview-Endpoint nutzt Fallback-Quelle:
  - primär: `<rtsp_url>#media=video`
  - fallback: `tent_{tent_id}` (go2rtc stream-name)
- Dadurch funktionieren Previews auch dann, wenn `rtsp_url` im Datensatz leer/inkonsistent ist, aber ein benannter go2rtc-Stream existiert.

## v0.154

### Feature
Preview-Bilder laufen jetzt über die API (gleiche Domain), damit go2rtc nicht öffentlich geöffnet werden muss.

### Änderungen
- Neuer Endpoint: `GET /tents/{tent_id}/preview`
  - Backend holt intern Bild von `GO2RTC_BASE_URL/api/frame.jpeg`
  - liefert JPEG direkt an den Browser zurück
- `GET /tents/{tent_id}/latest` gibt bei `preview_url` jetzt aus:
  - `/tents/{tent_id}/preview`
  - statt direktem `:1984` Link

### Ergebnis
- Frontend kann Previews über die App-Domain laden.
- go2rtc-Port muss nicht extern freigegeben werden.

## v0.153

### Fix
`Load failed: Chart is not defined` auf Systemen ohne externen CDN-Zugriff (z. B. Raspberry Pi) abgefangen.

### Ursache
Wenn `https://cdn.jsdelivr.net/npm/chart.js` beim Laden nicht erreichbar ist, war `Chart` undefiniert und das Dashboard brach mit Fehler ab.

### Änderungen
- Schutz eingebaut:
  - `buildCharts(...)` prüft `typeof Chart === 'undefined'` und bricht sauber ab (statt Exception), mit Statushinweis.
  - `buildSingleChart(...)` erstellt nur Charts, wenn `Chart` verfügbar ist.
  - `legendLabelsWithCurrent()` hat Fallback ohne Zugriff auf `Chart.defaults`.
- Ergebnis: kein JS-Absturz mehr, restliches Dashboard lädt weiter.

## v0.152

### UI
Button-Text für ESP-Statuslink umbenannt + Übersetzung angepasst.

### Änderungen
- `ESP stats` → `Open stats` (EN)
- `ESP Stats` → `Stats öffnen` (DE)
- Betrifft den Button neben `ESP öffnen`.
- Version auf `v0.152` erhöht.

## v0.151

### Fix
Alpha-History-Achsen/Legende ergänzt.

### Änderungen
- Alpha-Chart hat jetzt wieder klar sichtbare Skalenbeschriftung links/rechts:
  - linke Achse: `α Temp` (grün)
  - rechte Achse: `α Hum` (gelb)
- Beide Reihen laufen auf getrennten Achsen (`y`/`yR`) mit identischem Bereich `0..0.4`.
- Version auf `v0.151` erhöht.

## v0.150

### UI
Alpha-Temperature und Alpha-Humidity Verlauf zu einem gemeinsamen Chart zusammengeführt.

### Änderungen
- Ersetzt:
  - `Alpha Temperature History`
  - `Alpha Humidity History`
- Neu:
  - `Alpha History` mit zwei Linien in einem Chart:
    - `α Temp`
    - `α Hum`
- i18n angepasst:
  - EN: `Alpha History`
  - DE: `Alpha-Verlauf`
- Version auf `v0.150` erhöht.

## v0.149

### UI
Rohwerte unter den aktuellen Werten + gestrichelte Rohwert-Linien in den Histogrammen.

### Änderungen
- Aktuelle Karten erweitert:
  - unter `Temperatur` wird jetzt `Rohwert: ...` angezeigt
  - unter `Luftfeuchte` wird jetzt `Rohwert: ...` angezeigt
- Verlauf erweitert:
  - Temperatur-Histogramm: zusätzliche gestrichelte Rohwert-Linie in hellerer Farbe
  - Luftfeuchte-Histogramm: zusätzliche gestrichelte Rohwert-Linie in hellerer Farbe
- Raw-Linien basieren auf:
  - `temperature_raw`
  - `humidity_raw`
- Version auf `v0.149` erhöht.

## v0.148

### UI
Aktuelle Werte jetzt in allen Histogramm-Legenden sichtbar.

### Änderungen
- Für alle Charts wurde die Legende erweitert:
  - hinter jedem Legendeneintrag wird der **letzte gültige Wert** angezeigt.
  - Format: `<Label>: <aktueller Wert>`
- Gilt für Temperatur, Luftfeuchte, VPD, Alpha-Temperatur, Alpha-Luftfeuchte, DS18B20 und Gesamtverbrauch.
- Implementierung über gemeinsame Funktion `legendLabelsWithCurrent()` in der Dashboard-UI.

## v0.147

### Änderung auf Wunsch
Alpha-Werte **nicht** in Temperatur/Luftfeuchte-Chart überlagern, sondern als **separate Verlaufskarten** anzeigen.

### Änderungen
- Entfernt:
  - `α Temp` Overlay im Temperaturchart
  - `α Hum` Overlay im Luftfeuchtechart
- Neu:
  - separate Karte `Alpha Temperature History` (`alphaTempChart`)
  - separate Karte `Alpha Humidity History` (`alphaHumChart`)
- i18n ergänzt:
  - EN/DE Labels für beide neuen Verlaufskarten
- CSV-Erweiterung aus v0.146 bleibt bestehen (`effectiveAlfaTempC`, `effectiveAlfaHumPct`).
- Version auf `v0.147` erhöht.

## v0.146

### Feature
`effectiveAlfa`-Werte in Verlauf und CSV ergänzt.

### Änderungen
- History API (`/tents/{id}/history`) liefert jetzt zusätzlich je Punkt:
  - `effectiveAlfaTempC`
  - `effectiveAlfaHumPct`
- Verlaufscharts erweitert:
  - Temperatur-Chart enthält zusätzliche Linie `α Temp`
  - Feuchte-Chart enthält zusätzliche Linie `α Hum`
  - beide auf eigener rechter `α`-Achse (0..0.4)
- CSV-Export erweitert um Spalten:
  - `effectiveAlfaTempC`
  - `effectiveAlfaHumPct`
- Version auf `v0.146` erhöht.

## v0.145

### Frage
Für `sensors.cur.effectiveAlfaTempC` und `sensors.cur.effectiveAlfaHumPct` neben Temperatur/Luftfeuchte einen LED-ähnlichen Kreis anzeigen:
- < 0.10 grün
- 0.10–0.20 gelb
- > 0.20 rot

### Antwort
Erledigt: Neben den Labels `Temperatur` und `Luftfeuchte` werden jetzt farbige Alpha-LEDs angezeigt.

### Änderungen
- Neue UI-Elemente:
  - `#tempAlphaLed` neben `lblTemp`
  - `#humAlphaLed` neben `lblHum`
- Neue CSS-Klassen:
  - `alpha-led`, `alpha-led-green`, `alpha-led-yellow`, `alpha-led-red`, `alpha-led-off`
- Neue JS-Logik:
  - `setAlphaLed(id, alphaVal)`
  - liest Werte aus:
    - `sensors.cur.effectiveAlfaTempC`
    - `sensors.cur.effectiveAlfaHumPct`
  - setzt Farbe gemäß Schwellwerten
- Tooltip zeigt den Alpha-Wert (`α: <value>`).
- Version auf `v0.145` erhöht.

## v0.144

### Fix
`CSV exportieren` konnte mit Internal Server Error abbrechen.

### Ursache
Im Export-Loop wurden `timestamps/leaf_offsets` vor der Invalid-Filterung gefüllt, `raw`-Arrays aber erst nach Filter.
Dadurch entstanden bei verworfenen Samples unterschiedliche Array-Längen und Indexfehler.

### Änderungen
- `export_history_csv(...)` korrigiert:
  - `timestamps` + `leaf_offsets` werden jetzt **erst nach gültiger Sample-Validierung** angehängt.
- Ergebnis: konsistente Array-Längen, kein 500er beim CSV-Export.
- Version auf `v0.144` erhöht.

## v0.143

### Fix
ESP-Zusatzlink angepasst.

### Änderungen
- Linkziel geändert:
  - von `/api/stats`
  - auf `/api/state`
- Typografie angepasst:
  - `ESP öffnen` und `ESP Stats` jetzt nicht fett (`font-weight: 400`).
- Version auf `v0.143` erhöht.

## v0.142

### Fix
Ignore invalid startup sensor values in ingest/history/smoothing/export.

### Problem
Startup spikes (e.g. `181.7°C`) polluted smoothing state and appeared in history/CSV.

### Validation logic (applied before accept)
A sample is accepted only if all are true:
- `TEMP_MIN_C <= temperatureC <= TEMP_MAX_C` (default `-20..80`)
- `0 <= humidityPct <= 100`
- `VPD_MIN_KPA <= vpdKpa <= VPD_MAX_KPA` (default `0..6`)

(`vpdKpa` is derived from temp/humidity + leaf offset in pipeline.)

### Where applied
1. **Ingest (`save_state`)**
   - compute `raw_t/raw_h/raw_vpd`
   - if invalid: **return immediately**
     - no raw update
     - no smoothed update
     - no DB insert
     - no `cur.*` persistence for that sample
2. **History API (`/tents/{id}/history`)**
   - invalid rows are skipped before smoothing/point output
3. **CSV export (`/api/export`)**
   - invalid rows are skipped before raw/smoothed arrays are built

### Startup guard behavior
- Logging/smoothing starts only after the first valid sample.
- Invalid startup frames do not initialize EMA state.

### Configurable thresholds
Environment vars:
- `SENSOR_TEMP_MIN_C` (default `-20`)
- `SENSOR_TEMP_MAX_C` (default `80`)
- `SENSOR_VPD_MIN_KPA` (default `0`)
- `SENSOR_VPD_MAX_KPA` (default `6`)

### Version
- `v0.142`

## v0.141

### Frage
Neben `ESP öffnen` einen direkten Link auf `${ESP}/api/stats` anzeigen.

### Antwort
Erledigt: Im Header gibt es jetzt zusätzlich einen `ESP stats`-Link pro aktivem Zelt.

### Änderungen
- Dashboard-Header erweitert:
  - neuer Link `espStatsBtn` neben `espOpenBtn`
- URL-Logik:
  - Basis aus `source_url` des aktiven Zelts
  - Ziel: `<controller-base>/api/stats`
- i18n ergänzt:
  - EN: `ESP stats`
  - DE: `ESP Stats`
- Sichtbarkeit wie bei `ESP öffnen` (nur wenn URL vorhanden).
- Version auf `v0.141` erhöht.

## v0.140

### Fix
Raw vs. smoothed sensor pipeline corrected (temperature/humidity/VPD) for storage, API, and CSV export.

### Bug location
- `export_history_csv(...)` wrote smoothed values into both the default and smoothed columns, and raw source mapping only used `sensors.cur.*`.
- Result: `*_raw` and `*_smoothed` looked identical in export.

### Why raw and smoothed were identical
- The CSV writer used `temp_sm/hum_sm/vpd_sm` for the generic fields and repeated those same arrays again in `*_smoothed`.
- No dedicated persisted raw/smoothed channels existed in `tent_state` payload before this fix.

### Changes
- Added explicit raw/smoothed storage on ingest (`save_state`):
  - `sensors.raw.temperatureC`, `sensors.raw.humidityPct`, `sensors.raw.vpdKpa`
  - `sensors.smoothed.temperatureC`, `sensors.smoothed.humidityPct`, `sensors.smoothed.vpdKpa`
- Implemented EMA smoothing in backend (`EMA_ALPHA`, `_ema_next`, per-tent `EMA_STATE`).
- Implemented explicit VPD calculation helper (`_calc_vpd_kpa`) and dual VPD calculation:
  - `vpd_raw = calc(rawTemp, leafOffset, rawHumidity)`
  - `vpd_smoothed = calc(smoothedTemp, leafOffset, smoothedHumidity)`
- Updated `/tents/{tent_id}/history` points to include (without breaking existing fields):
  - `temperature`, `temperature_raw`, `temperature_smoothed`
  - `humidity`, `humidity_raw`, `humidity_smoothed`
  - `vpd`, `vpd_raw`, `vpd_smoothed`
  - existing `temp/hum/vpd` remain for compatibility (mapped to smoothed)
- Updated `/api/export` CSV mapping to use real raw values and EMA-smoothed values separately.

### Compatibility
- Existing API consumers using `temp/hum/vpd` continue to work.
- New explicit fields were added; structure not removed.

### Verification expectation
- In normal operation, `*_raw` and `*_smoothed` now diverge naturally under sensor noise/transients.
- If input is perfectly stable, values can still match (expected mathematically).

## v0.139

### Frage
Gastmodus-Badge im Header bitte mittig und rot darstellen.

### Antwort
Erledigt: Der Gastmodus-Hinweis sitzt jetzt mittig im Header und ist rot hervorgehoben.

### Änderungen
- Header angepasst:
  - Badge als zentriertes Element (`guest-badge-center`) in der Header-Mitte
- Styling angepasst:
  - rote Hervorhebung (Border/Background/Text)
- Übersetzung bleibt erhalten:
  - DE: `Gastmodus aktiv`
  - EN: `Guest mode active`
- Version auf `v0.139` erhöht.

## v0.138

### Frage
Im Header sichtbar anzeigen, wenn Gastmodus aktiv ist (mit Übersetzung).

### Antwort
Erledigt: Im App-Header erscheint jetzt ein Badge bei aktivem Gastmodus.

### Änderungen
- Neuer Header-Badge im App-Shell:
  - DE: `Gastmodus aktiv`
  - EN: `Guest mode active`
- Sichtbarkeit abhängig von Rolle (`/auth/whoami`):
  - role=guest => Badge sichtbar
  - sonst verborgen
- Text aktualisiert sich sprachabhängig (DE/EN).
- Version auf `v0.138` erhöht.

## v0.137

### Fix
Gastmodus-UI-Sperre kam verzögert; `ESP öffnen` blieb kurz klickbar.

### Änderungen
- Dashboard startet jetzt mit `role-pending` (Sperre sofort aktiv bis Rollencheck fertig ist).
- `applyGuestModeUi()` auf Rollenklassen umgestellt:
  - `role-pending` / `role-guest` / `role-admin`
- CSS-Sperre ergänzt für:
  - alle Buttons (außer ViewMode/MobileNav)
  - `#espOpenBtn`, `#streamOpenBtn`, `.shelly-open-btn`
- Ergebnis:
  - keine Klickfenster mehr vor Abschluss des Rollenchecks
  - `ESP öffnen` ist im Gastmodus zuverlässig nicht klickbar.
- Version auf `v0.137` erhöht.

## v0.136

### Fix
Im Gastbereich fehlte ein eigener Speichern-Button.

### Änderungen
- Neuer Button im Access-Bereich:
  - `saveGuestBtn` (`Save guest` / `Gast speichern`)
- i18n ergänzt (`saveGuest` in EN/DE).
- Der Button triggert das bestehende Access-Speichern, sodass Gastdaten direkt gespeichert werden.
- Version auf `v0.136` erhöht.

## v0.135

### Frage
Gastmodus für reine Ansicht ohne Änderungen:
- eigene Gast-Credentials
- definierbare Ablaufzeit
- Config für Gast nicht erreichbar
- alle Buttons deaktiviert

### Antwort
Gastmodus ist implementiert (read-only) mit eigener Login-Kennung und Ablaufzeit.

### Änderungen
- Auth/DB erweitert (`app_auth_config`):
  - `guest_enabled`
  - `guest_username`
  - `guest_password_hash`
  - `guest_expires_at`
- Login erweitert:
  - Gast-Login prüft eigene Credentials + Ablaufzeit
  - abgelaufene Gast-Zugänge werden abgewiesen
  - Session-Rolle `guest`
- Middleware-Rechteschutz für Gäste:
  - `GET` erlaubt (Read-only)
  - alle schreibenden Requests blockiert (`403`)
  - `/config/*` und `/setup` für Gast gesperrt
- Neue Endpoint-Info:
  - `GET /auth/whoami` (Rolle/Session-Info)
- Setup (`Access`) erweitert um Gastmodus-Konfiguration:
  - Gast aktivieren
  - Gast-Benutzername
  - Gast-Passwort
  - `guest_expires_at` (datetime)
- Dashboard UI:
  - in Gastmodus werden Buttons deaktiviert (nur Ansicht)
- Version auf `v0.135` erhöht.

## v0.134

### Frage
Bitte Hinweis anzeigen, solange History noch aufgebaut wird (inkl. Übersetzung).

### Antwort
Eingebaut: Bei wenigen Datenpunkten erscheint jetzt ein lokalisierter Build-up-Hinweis.

### Änderungen
- Neue i18n-Texte:
  - EN: `History is still building up…`
  - DE: `Historie wird noch aufgebaut…`
- Statuslogik im Dashboard:
  - bei `points.length < 30` wird der Build-up-Hinweis angezeigt
  - danach wieder normales Statusverhalten
- Version auf `v0.134` erhöht.

## v0.133

### Frage
Es gibt noch keine Option zum Löschen von Zelten.

### Antwort
Ich habe eine Löschfunktion für Zelte ergänzt (Backend + Setup-UI).

### Änderungen
- Neue API-Route:
  - `DELETE /tents/{tent_id}`
- Service/DB ergänzt:
  - `TentService.delete_tent(...)`
  - `crud.delete_tent_raw(...)`
- Setup-UI (`/setup`) erweitert:
  - pro Zelt neuer `Delete`-Button
  - Sicherheitsabfrage per `confirm(...)`
  - nach Erfolg Reload der Zeltliste
- Version auf `v0.133` erhöht.

## v0.132

### Frage
Kann `POLL_URL`/Default-Tent-Source bei Neuinstallation komplett raus?

### Antwort
Ja. Beides ist entfernt, damit ein frisches System ohne vorgegebene Controller-IP startet.

### Änderungen
- `docker-compose.yml`:
  - `POLL_URL` Environment-Variable entfernt.
- Backend-Init:
  - Auto-Insert von `Tent 1` mit Default-`source_url` entfernt.
  - Keine Default-Zeltanlage mehr in `init_db()`.
- `api/core/config.py`:
  - `POLL_URL` Default auf leer (`""`) gesetzt.
- Version auf `v0.132` erhöht.

## v0.131

### Frage
In der VPD-Kachel bitte nur `min:` anzeigen.

### Antwort
Erledigt: In der VPD-Kachel wird jetzt nur noch `min:` verwendet.

### Änderungen
- Neuer i18n-Shortkey `minShort` (`min`) eingeführt.
- VPD-Kachel (`vpdTarget`) nutzt für die zweite Zeile jetzt:
  - `min: <Wert>`
- Plan-Dialog-Label (`Min. VPD`) bleibt unverändert.
- Version auf `v0.131` erhöht.

## v0.130

### Frage
`VPD (kPa)` bitte entfernen.

### Antwort
Erledigt: Die Beschriftung wurde gekürzt.

### Änderungen
- i18n Label `minVpd` angepasst:
  - EN: `Min VPD`
  - DE: `Min. VPD`
- Damit verschwindet `(kPa)` in der UI (Kachel/Plan-Label).
- Version auf `v0.130` erhöht.

## v0.129

### Frage
`Min. VPD` lieber unter `Sollwert`, damit die VPD-Kachel nicht zu eng wird.

### Antwort
Layout angepasst: `Min. VPD` steht jetzt direkt unter `Sollwert`.

### Änderungen
- `vpdTarget`-Layout neu angeordnet:
  - linke Seite zweizeilig:
    - `Sollwert`
    - `Min. VPD`
  - rechte Seite:
    - `Blatt-Offset`
- Schriftgröße bleibt wie bisher in der small-Zeile.
- Version auf `v0.129` erhöht.

## v0.128

### Frage
Werte der `min. VPD Überwachung` in die aktuelle VPD-Kachel einbinden — oberhalb von `Blatt-Offset`, gleiche Schriftgröße.

### Antwort
Erledigt: In der VPD-Info steht jetzt zusätzlich `Min. VPD` oberhalb von `Blatt-Offset` in gleicher Größe.

### Änderungen
- `vpdTarget`-Anzeige erweitert:
  - linke Seite: `Target`
  - rechte Seite (zweizeilig, gleiche small-font):
    - `Min. VPD: <Wert>`
    - `Blatt-Offset: <Wert>`
- Datenquelle:
  - `currentExhPlan.min_vpd_kpa` aus `/tents/{id}/exhaust-vpd-plan`
- `currentExhPlan` wird beim Plan-Refresh und nach Plan-Speichern aktualisiert.
- Version auf `v0.128` erhöht.

## v0.127

### Frage
Shelly-Geräte-Buttons sind in unterschiedlicher Höhe. In jeder Kachel sollen sie unten stehen.

### Antwort
Gefixt: Die Action-Buttons in Shelly-Karten sind jetzt bottom-aligned.

### Änderungen
- `#shellyDevices .card` auf flex-column umgestellt.
- `.shelly-actions` mit `margin-top:auto` + `padding-top` gesetzt.
- Ergebnis: Toggle/Open-Shelly Buttons stehen in allen Shelly-Kacheln konstant unten.
- Version auf `v0.127` erhöht.

## v0.126

### Frage
Relais-Buttons (inkl. Bewässerungsrelais 6-8) sollen im gleichen Stil wie `min. VPD Überwachung` dargestellt werden.

### Antwort
Erledigt: Die Relais-Buttons nutzen jetzt denselben visuellen Button-Stil (Gradient, Hover, Press) und Farb-Logik grün/rot.

### Änderungen
- CSS für `.relay`, `.on`, `.off` überarbeitet:
  - gleicher Button-Look wie Plan-Buttons (Gradient + Schatten + Hover/Active)
  - `on` = grün
  - `off` = rot
- Gilt für beide Bereiche:
  - Relais 1–5
  - Bewässerungsrelais 6–8
- Version auf `v0.126` erhöht.

## v0.125

### Frage
`min. VPD Überwachung`-Button flackert zwischen rot und grün.

### Antwort
Gefixt: Das Flackern kam von einem kurzzeitigen Reset auf Rot vor jedem Async-Reload der Plan-States.

### Änderungen
- `refreshPlanButtonStates()` angepasst:
  - entferntes Vorab-Reset von IR/Exhaust-Plan-Buttons auf Rot
  - Buttonfarbe wird jetzt erst nach erfolgreicher API-Antwort gesetzt
    - aktiviert => Grün
    - deaktiviert => Rot
  - bei Fetch-Fehler bleibt die letzte gültige Farbe bestehen (kein visuelles Flackern)
- Version auf `v0.125` erhöht.

## v0.124

### Frage
`Stream update:` soll nur den Zeitstempel anzeigen — ohne `vor ...` und ohne Klammern.

### Antwort
Angepasst: Stream-Update zeigt jetzt nur noch die Uhrzeit als Zeitstempel.

### Änderungen
- Dashboard Stream-Info:
  - `Stream update: HH:MM:SS`
- Vollbild-Header:
  - `Stream update: HH:MM:SS`
- Entfernt:
  - relative Zeit (`vor ...`)
  - Klammerformat
- Version auf `v0.124` erhöht.

## v0.123

### Frage
Bei `Kamera-Stream -> Vollbild öffnen` geht das Bild sporadisch kaputt (broken JPG). Gewünscht:
- nur auf neues gültiges Bild aktualisieren
- Update-Zeit wie bei aktuellen Werten
- Text `Stream update` mit Zeit anzeigen

### Antwort
Ich habe den Stream-Refresh robuster gemacht und die Update-Anzeige ergänzt.

### Änderungen
- Preview-Refresh (Dashboard) umgestellt auf **preload-then-swap**:
  - neues JPEG wird erst unsichtbar geladen
  - nur bei `onload` wird das sichtbare Bild ersetzt
  - bei `onerror` bleibt das letzte gültige Bild stehen (kein broken icon)
- Vollbild-Preview ebenfalls auf preload-then-swap umgestellt.
- Neue i18n-Bezeichnung:
  - `streamUpdate` (DE/EN: `Stream update`)
- Anzeige erweitert:
  - Dashboard-Info zeigt jetzt `Stream update: vor X Min (HH:MM:SS)`
  - Vollbild-Header zeigt ebenfalls `Stream update: ...`
- Version auf `v0.123` erhöht.

## v0.122

### Frage
`Vollbild öffnen` übernimmt Theme nicht (bleibt immer Dark Mode).

### Antwort
Gefixt: Das Vollbild-Preview übernimmt jetzt das aktive Theme (Light/Dark).

### Änderungen
- Popup-Preview (`streamOpenBtn`) nutzt nun `gt_theme` aus `localStorage`.
- Farbschema im Vollbild wird dynamisch für Light/Dark gesetzt (Body/Header/Stage/Button/Text).
- Sprachabhängige Titel/Button-Texte im Popup (`Preview/Vorschau`, `Close/Schließen`).
- Update-Zeitstempel im Popup nutzt i18n-Key `updated` statt hartem `Update`.
- Version auf `v0.122` erhöht.

## v0.121

### Fix
Backup-Export/Import lieferte `{"detail":"Not Found"}` trotz Setup-Button.

### Ursache
Die neuen Backup-Endpunkte waren nur im Legacy-`app.py` definiert, aber der laufende Einstiegspunkt (`main.py`) nutzt Router aus `api/routes/*`.

### Änderungen
- `api/routes/system.py` erweitert:
  - `GET /config/backup/export` -> delegiert auf `legacy.export_config_backup()`
  - `POST /config/backup/import` -> delegiert auf `legacy.import_config_backup(payload)`
- Version auf `v0.121` erhöht.

## v0.120

### Frage
Button `CSV exportieren` ins Zeltfenster verschieben — zwischen `Laufzeit` und `ESP öffnen`.

### Antwort
Erledigt. Der CSV-Button ist jetzt im Dashboard-Titelbereich des Zeltfensters positioniert.

### Änderungen
- Entfernt aus App-Shell-Header (`/app`):
  - `shellExportBtn`
- Hinzugefügt im Dashboard-Zeltfenster (`/dashboard`):
  - `exportCsvBtn` zwischen `uptimeBadge` (Laufzeit) und `espOpenBtn` (ESP öffnen)
- i18n-Anbindung für Buttonlabel wieder aktiv (`exportCsv`).
- Export-Verhalten im Dashboard:
  - `GET /api/export?tent_id=<currentTentId>&range=<24h|7d|all>`
  - Range wie bisher aus `gt_range_minutes` abgeleitet.
- Version auf `v0.120` erhöht.

## v0.119

### Frage
Im Setup ein Konfigurations-Backup des gesamten CanopyOps erstellen und auf einer neuen Maschine importieren.

### Antwort
Ich habe Export/Import für Konfigurations-Backups im Setup integriert.

### Änderungen
- Neue API-Endpunkte:
  - `GET /config/backup/export`
    - exportiert JSON-Backup mit:
      - allen `tents`-Konfigurationen (inkl. Plänen, Shelly-Credentials, IDs)
      - `app_auth_config` (Auth/2FA-Konfiguration inkl. Hash/Secret/Recovery-Daten)
      - Metadaten (`kind`, `schema_version`, `app_version`, `exported_at`)
  - `POST /config/backup/import`
    - validiert Backup-Kind
    - ersetzt Tent-Konfigurationen atomar
    - stellt Auth/2FA-Konfiguration wieder her
    - setzt Serial-Sequenz für `tents.id` korrekt nach
- Setup-UI erweitert:
  - neue Backup-Karte mit:
    - `Export backup`
    - Dateiauswahl für JSON
    - `Import backup`
  - DE/EN i18n-Labels ergänzt.
- Version auf `v0.119` erhöht.

## v1.18

### Frage
Für `Nächste` bitte Option 2: Zeit aus `settings.shelly.light.line` verwenden; wenn nicht vorhanden, leer (`-`) statt aktueller Aktivierungszeit.

### Antwort
Ich habe die Next-Run-Berechnung im UI entsprechend angepasst.

### Änderungen
- `computeNextIrrigationDate(...)`:
  - nutzt jetzt ausschließlich den ON-Zeitpunkt aus `settings.shelly.light.line`
  - wenn ON-Zeit nicht parsebar/fehlt: Rückgabe `null` → Anzeige bleibt `-`
- Entferntes Verhalten:
  - kein Fallback mehr auf aktuelle Uhrzeit beim Aktivieren.
- Version auf `v1.18` erhöht.

## v1.17

### Frage
Kann der Startzeitpunkt am Bewässerungstag auf den tatsächlichen Licht-ON-Zeitpunkt geprüft und mit `Minuten nach Licht an` Offset berechnet werden?

### Antwort
Ja. Der Scheduler nutzt jetzt bevorzugt den echten Licht-ON-Zeitpunkt aus der Tageshistorie und wendet darauf den Offset an.

### Änderungen
- Neuer Helper:
  - `_find_light_on_today_dt(tent_id)`
  - erkennt den heutigen Übergang `cur.shelly.light.isOn: false -> true` aus `tent_state`
- `_try_run_irrigation_schedule(...)` angepasst:
  - bevorzugt tatsächliches `light_on_dt + offset`
  - fallback bleibt: konfigurierter ON-Zeitplan aus `settings.shelly.light.line`
- Zeitzonenvergleich robust gemacht (aware/naive Datetime).
- Version auf `v1.17` erhöht.

## v1.16

### Frage
Beim Aktivieren des Bewässerungsplans soll der Start sinnvoll ab morgen erfolgen (bzw. wenn heute schon bewässert wurde, entsprechend angepasst). Außerdem soll `Nächste` nicht leer bleiben.

### Antwort
Ich habe die Plan-Aktivierungslogik und die Next-Run-Berechnung verbessert.

### Änderungen
- DB/Plan-Update (`update_irrigation_plan_raw`):
  - Beim erstmaligen Aktivieren wird `irrigation_last_run_date` auf heute gesetzt (falls noch leer/älter), damit der reguläre Plan ab dem nächsten Tag startet.
  - Wenn heute bereits bewässert wurde (Datum heute), bleibt es konsistent.
  - Response enthält jetzt `last_run_date`.
- Frontend-Next-Berechnung (`computeNextIrrigationDate`):
  - Falls keine Licht-ON-Zeit erkannt wird, nutzt die Berechnung eine sinnvolle Fallback-Zeit (aktuelle lokale Zeit), statt leer zu bleiben.
- Nach Plan-Speichern:
  - `currentIrPlan` und `currentIrLastRunDate` werden aus der API-Response aktualisiert.
  - `loadLatest()` wird direkt aufgerufen, damit `Nächste` sofort sichtbar/aktuell ist.
- Version auf `v1.16` erhöht.

## v1.15

### Frage
`Nächste Bewässerung` soll zu `Nächste` gekürzt werden.

### Antwort
Ich habe die Label-Texte gekürzt.

### Änderungen
- DE: `Nächste Bewässerung` -> `Nächste`
- EN: `Next irrigation` -> `Next`
- Version auf `v1.15` erhöht.

## v1.14

### Frage
`Letzte Bewässerung` aus der Zeile `Restzeit · Endzeit` entfernen und stattdessen in `Nächste Bewässerung` integrieren — dort nur mit kurzem Text `Letzte`.

### Antwort
Ich habe die Anzeige entsprechend umgebaut.

### Änderungen
- `irTimeLine` zeigt wieder nur:
  - `Restzeit · Endzeit`
- `irNextRun` zeigt jetzt kombiniert:
  - `Nächste Bewässerung: <...> · Letzte: <...>`
- Neue i18n-Kurzbezeichnung:
  - EN: `Last`
  - DE: `Letzte`
- Version auf `v1.14` erhöht.

## v1.13

### Frage
In der Bewässerungszeile (`Restzeit · Endzeit`) zusätzlich anzeigen, wann die letzte Bewässerung war (mit Tag).

### Antwort
Ich habe die Zeile erweitert und den letzten Lauf mit Wochentag ergänzt.

### Änderungen
- Neue Übersetzungstexte:
  - EN: `Last irrigation`
  - DE: `Letzte Bewässerung`
- Neue Format-Hilfe:
  - `formatLastRunDate(isoDate)` → lokalisierte Tages-/Datumsanzeige
- `irTimeLine` zeigt jetzt:
  - `Restzeit`
  - `Endzeit`
  - `Letzte Bewässerung` (mit Tag/Datum)
- Datenquelle bleibt `irrigation_last_run_date` aus Plan-Status.
- Version auf `v1.13` erhöht.

## v1.12

### Frage
`CSV exportieren` soll im App-Header zwischen `Mobile Ansicht` und `Logout` stehen.

### Antwort
Ich habe den Export-Button in die Header-Leiste des App-Shell verschoben und zwischen View-Mode und Logout platziert.

### Änderungen
- Neuer Header-Button im App-Shell:
  - ID: `shellExportBtn`
  - Position: zwischen `shellViewModeBtn` und `logoutBtn`
- Lokalisierte Beschriftung:
  - DE: `CSV exportieren`
  - EN: `Export CSV`
- Klickverhalten:
  - Download via `/api/export?tent_id=<current>&range=24h`
  - aktuelles Tent wird aus URL (`tent`) oder `localStorage(gt_tent_id)` bestimmt
- Alten Dashboard-Karten-Exportbutton entfernt, damit es keine Doppelung gibt.
- Version auf `v1.12` erhöht.

## v1.11

### Frage
CSV-Export soll zusätzlich enthalten:
- smoothed values (temperature, humidity, VPD)
- raw values (falls vorhanden)

### Antwort
Ich habe den CSV-Export erweitert: Er enthält jetzt sowohl rohe als auch geglättete Sensordaten.

### Änderungen
- `export_history_csv(...)` erweitert:
  - sammelt `temperature/humidity/vpd` als Raw-Werte aus Historie
  - berechnet geglättete Werte mit dem bestehenden Despike-Ansatz
- CSV-Spalten jetzt:
  - `timestamp`
  - `temperature`, `humidity`, `vpd` (smoothed)
  - `temperature_raw`, `humidity_raw`, `vpd_raw`
  - `temperature_smoothed`, `humidity_smoothed`, `vpd_smoothed`
- Version auf `v1.11` erhöht.

## v1.10

### Frage
Download-Button für historische Sensordaten ergänzen (CSV, timestamp/temperature/humidity/VPD), mit Endpoint `/api/export` und Dateiname inkl. Datum/Uhrzeit.

### Antwort
Ich habe einen CSV-Export-Endpoint und einen UI-Button eingebaut.

### Änderungen
- Neuer API-Endpoint:
  - `GET /api/export?tent_id=<id>&range=<24h|7d|all|minutes>`
- Export enthält CSV-Spalten:
  - `timestamp`
  - `temperature`
  - `humidity`
  - `vpd`
- Datenquelle:
  - bestehende `tent_state`-Historie aus PostgreSQL
- Dateiname enthält Datum/Zeit:
  - `tent_<id>_history_<range>_YYYYMMDD_HHMMSS.csv`
- UI:
  - neuer Button `Export CSV` im Dashboard
  - Button triggert Download gegen `/api/export`
  - Range wird aus vorhandener Historienauswahl abgeleitet (24h/7d/all).
- Version auf `v1.10` erhöht.

## v1.09

### Frage
Wenn man manuell mit `Bewässerung starten` startet, soll der Bewässerungsplan entsprechend angepasst werden, damit nicht direkt am nächsten Tag erneut ungewollt gestartet wird.

### Antwort
Ich habe den manuellen Start so erweitert, dass bei erfolgreichem `startWatering` auch `irrigation_last_run_date` auf heute gesetzt wird.

### Änderungen
- Endpoint `POST /tents/{tent_id}/actions/startWatering`:
  - nach erfolgreichem Start (`ok=true`) wird `tents.irrigation_last_run_date = today` gespeichert
  - Response enthält zusätzlich `irrigation_last_run_date`
- Dadurch berücksichtigt der Plan den manuellen Start als letzten Lauf.
- Version auf `v1.09` erhöht.

## v1.08

### Frage
Buttons bei `min. VPD Überwachung` und `Bewässerungsplan` farblich klar markieren: grün wenn aktiv, rot wenn nicht aktiv.

### Antwort
Ich habe die Plan-Buttons farbcodiert:
- aktiv = grün
- nicht aktiv = rot

### Änderungen
- `refreshPlanButtonStates()` angepasst:
  - `activeStyle` auf grün gesetzt
  - `inactiveStyle` auf rot gesetzt
  - beide Buttons starten mit rot und wechseln auf grün, wenn jeweiliger Plan aktiv ist.
- Betrifft:
  - `openIrPlanBtn` (Bewässerungsplan)
  - `openExhVpdPlanBtn` (min. VPD Überwachung)
- Version auf `v1.08` erhöht.

## v1.07

### Frage
In der Irrigation-Kachel oberhalb von `Runs left` eine Zeile ergänzen, wann die nächste Bewässerung angestoßen wird (inkl. Tag/Datum/Zeit je Sprache).

### Antwort
Ich habe in der Irrigation-Kachel eine neue `Nächste Bewässerung / Next irrigation`-Zeile ergänzt und berechne den nächsten geplanten Zeitpunkt aus Plan + Licht-ON + Offset.

### Änderungen
- Neue UI-Zeile in Irrigation-Kachel:
  - `irNextRun` oberhalb von `irRunsLeft`
- Neue Frontend-Helper:
  - `parseLightOnMinFromLine(...)`
  - `computeNextIrrigationDate(plan, lastRunDate, lightLine)`
  - `formatNextRunDate(...)` (lokalisiert: DE/EN mit Wochentag + Datum + Uhrzeit)
- Plan-Status-Refresh speichert jetzt auch:
  - `currentIrPlan`
  - `currentIrLastRunDate`
- Anzeige wird in `loadLatest()` aktualisiert (nur 8x-Relays relevant).
- Version auf `v1.07` erhöht.

## v1.06

### Frage
`min. VPD monitoring` vorne mit kleinem `m` und nur bei 8x-Relays anzeigen.

### Antwort
Ich habe die Bezeichnung angepasst und den Button auf 8x-Relays begrenzt.

### Änderungen
- Text angepasst:
  - EN: `min. VPD monitoring`
  - DE: `min. VPD Überwachung`
- Button `openExhVpdPlanBtn` wird jetzt nur bei `settings.active_relay_count == 8` angezeigt.
- Version auf `v1.06` erhöht.

## v1.05

### Frage
Bitte `Exhaust VPD plan` in `Min. VPD Überwachung` umbenennen und bei aktivem Plan den Button rot markieren (auch beim Irrigation plan).

### Antwort
Ich habe die Bezeichnung angepasst und die Plan-Buttons bei aktivem Zustand rot markiert.

### Änderungen
- Umbenennung (DE/EN):
  - DE: `Min. VPD Überwachung`
  - EN: `Min. VPD monitoring`
- Dashboard-Buttons:
  - neuer Zustand-Refresh `refreshPlanButtonStates()`
  - liest Plan-Status über:
    - `GET /tents/{id}/irrigation-plan`
    - `GET /tents/{id}/exhaust-vpd-plan`
  - markiert aktive Plan-Buttons mit rotem Hintergrund
- Irrigation-Button im Card-Action-Bereich bekam stabile ID (`openIrPlanBtn`) für gezieltes Styling.
- Version auf `v1.05` erhöht.

## v1.04

### Frage
Alle Shellys von `/api/state` auf direkten Zugriff umstellen.

### Antwort
Ich habe den Dashboard-Read-Pfad auf direkten Sammelzugriff umgestellt: Alle konfigurierten Shelly-Geräte werden jetzt per Direct-Read geholt und über die `/api/state`-Werte gelegt.

### Änderungen
- Neuer Endpoint:
  - `GET /tents/{tent_id}/shelly/direct-all`
  - liest alle erkannten Shelly-Keys (`main`, `light`, `humidifier`, `heater`, `fan`, `exhaust` + dynamische Keys) direkt vom Shelly
- Neuer Helper:
  - `_get_shelly_direct_state_for_key(payload, tent, key)`
- Dashboard `loadLatest()`:
  - nutzt jetzt `shelly/direct-all`
  - mapped direkte Werte für `cur.shelly.<key>.isOn/Watt/Wh`
  - damit werden alte /api/state-Werte aktiv überschrieben
- Bestehende Action-Endpunkte bleiben kompatibel.
- Version auf `v1.04` erhöht.

## v1.03

### Frage
Können extreme Spikes in den Historienwerten herausgefiltert werden?

### Antwort
Ja — ich habe einen Spike-Filter im History-Endpoint ergänzt, der starke Ausreißer glättet.

### Änderungen
- Neuer interner Despike-Helper: `_despike_series(...)`
- Endpoint `GET /tents/{tent_id}/history` erweitert:
  - neuer Query-Parameter `filter_spikes` (Default: `1` = aktiv)
- Gefiltert werden jetzt (bei aktivem Filter):
  - `temp`, `hum`, `vpd`, `extTemp`
- Ausreißer werden auf den zuletzt plausiblen Wert begrenzt (statt harter Peaks).
- Response enthält zusätzlich `filter_spikes` zur Transparenz.
- Version auf `v1.03` erhöht.

## v1.02

### Frage
Die restlichen Tent-Plan-Operationen (`irrigation-plan`, `exhaust-vpd-plan`) ebenfalls komplett auf `service -> db.crud` umstellen.

### Antwort
Ich habe die Plan-Operationen jetzt konsistent auf den Layering-Pfad Route -> Service -> DB-Crud umgestellt.

### Änderungen
- `db/crud.py` erweitert um rohe Query-Funktionen:
  - `get_irrigation_plan_raw`
  - `update_irrigation_plan_raw`
  - `get_exhaust_vpd_plan_raw`
  - `update_exhaust_vpd_plan_raw`
- `services/tent_service.py` angepasst:
  - nutzt für diese vier Plan-Operationen jetzt `db.crud` statt Legacy-Aufrufe
- `routes/tents.py` bleibt dünn und unverändert delegierend an den Service.

## v1.01

### Frage
Service-Layer zwischen Routes und Datenbank sicherstellen:
- Routes greifen nicht direkt auf DB zu
- Services enthalten Business-Logik
- DB-Layer enthält nur Query-Zugriffe

### Antwort
Ich habe den modularen Layering-Schritt nachgezogen und die Kern-Tent-Pfade auf Service -> DB-Crud umgestellt.

### Änderungen
- `db/crud.py` enthält jetzt rohe SQL-Queries für Kernoperationen:
  - `list_tents_raw`
  - `create_tent_raw`
  - `update_tent_raw`
- `services/tent_service.py` nutzt diese CRUD-Funktionen für die Kern-Tent-Endpunkte.
- `routes/tents.py` bleibt dünn und delegiert weiterhin nur an `TentService`.
- Damit ist der Zugriffspfad für diese Kernoperationen sauber getrennt:
  - Route -> Service -> DB (SQL)

## v1.00

### Frage
In der VPD-Kachel neben `Sollwert: 0.80 kPa` rechts zusätzlich `settings.grow.offsetLeafTemperature` anzeigen.

### Antwort
Ich habe die Sollwert-Zeile in der VPD-Kachel auf zweispaltige Anzeige erweitert und den Leaf-Offset rechts ergänzt.

### Änderungen
- VPD-Zeile zeigt jetzt links/rechts:
  - links: `Sollwert: <targetVPD> kPa`
  - rechts: `Leaf offset / Blatt-Offset: <settings.grow.offsetLeafTemperature>°C`
- Fallback bei fehlendem Wert: `-`
- DE/EN Übersetzungen ergänzt (`leafOffset`).
- Version auf `v1.00` erhöht.

## v0.99

### Frage
Abluft triggert weiterhin nicht.

### Antwort
Ich habe die Shelly-Auth-Strategie erweitert: Neben BasicAuth wird jetzt auch DigestAuth probiert (plus optional ohne Auth). Das adressiert Shelly-Setups, die Basic ablehnen und Digest erwarten.

### Änderungen
- Neue Helper-Strategie: `_shelly_auth_candidates(user, pw)`
  - Reihenfolge: BasicAuth → DigestAuth → ohne Auth
- Auf diese Strategie umgestellt:
  - `_refresh_main_shelly_in_payload(...)`
  - `get_main_shelly_direct_state(...)`
  - `toggle_main_shelly_direct(...)`
  - `_read_exhaust_shelly_output(...)`
  - `_get_exhaust_shelly_direct_state_from_payload(...)`
  - `_set_exhaust_shelly_output(...)`
- Ziel: 401-Probleme zwischen Main/Abluft durch Auth-Mechanik harmonisieren und VPD-Trigger wieder funktionsfähig machen.
- Version auf `v0.99` erhöht.

## v0.98

### Frage
Bitte auch den Hauptschalter auf `Shelly.GetStatus` umstellen.

### Antwort
Ich habe den Main-Shelly-Statuspfad auf `GET /rpc/Shelly.GetStatus` umgestellt.

### Änderungen
- Main Direct-State (`get_main_shelly_direct_state`) liest Gen2 jetzt über:
  - `GET /rpc/Shelly.GetStatus`
  - Parsing aus `switch:0.*`
- Poller-Refresh für Main-History (`_refresh_main_shelly_in_payload`) liest Gen2 ebenfalls über:
  - `GET /rpc/Shelly.GetStatus`
  - `switch:0.apower`, `switch:0.aenergy.total`
- Version auf `v0.98` erhöht.

## v0.97

### Frage
Der korrekte Status-Read ist `http://<ip>/rpc/Shelly.GetStatus`.

### Antwort
Ich habe die Abluft-Direct-Statusabfrage auf `Shelly.GetStatus` umgestellt.

### Änderungen
- Für Abluft Gen2 wird jetzt gelesen über:
  - `GET /rpc/Shelly.GetStatus`
- Parsing angepasst auf:
  - `switch:0.output` (Status)
  - `switch:0.apower` (W)
  - `switch:0.aenergy.total` (Wh)
- Gilt für:
  - `_read_exhaust_shelly_output(...)`
  - `_get_exhaust_shelly_direct_state_from_payload(...)`
- Version auf `v0.97` erhöht.

## v0.96

### Frage
Controller-Toggle-Fallback für Abluft entfernen; Shelly direkt steuern. Trigger funktioniert weiterhin nicht.

### Antwort
Ich habe den Controller-Fallback entfernt (nur noch direkte Shelly-Steuerung) und zusätzliche Diagnose-Logs ergänzt.

### Änderungen
- Entfernt:
  - Fallback `POST /shelly/exhaust/toggle` über Controller in der VPD-Automation.
- Aktiv:
  - nur direkte Shelly-ON/OFF-Steuerung für Abluft.
- Verbesserte Diagnose:
  - Logs bei fehlgeschlagenem Direkt-Read/Set der Abluft (`[exhaust-direct-read]`, `[exhaust-direct-set]`).
  - Scheduler-Log bei nicht ausführbarem Soll-Set bleibt aktiv.
- Version auf `v0.96` erhöht.

## v0.95

### Frage
Abluft-Plan triggert weiterhin nicht.

### Antwort
Ich habe einen zusätzlichen robusten Fallback eingebaut: Wenn das direkte ON/OFF-Set am Shelly fehlschlägt, wird über den Controller (`/shelly/exhaust/toggle`) geschaltet.

### Änderungen
- Neue Fallback-Hilfsfunktion:
  - `_toggle_exhaust_via_controller(tent)`
- In `_try_run_exhaust_vpd_control(...)`:
  - primär: direkter Shelly Set (ON/OFF)
  - fallback: Controller-Toggle bei Set-Fehler
- Debug-Log ergänzt, wenn beide Wege fehlschlagen.
- Version auf `v0.95` erhöht.

## v0.94

### Frage
Abluft-Plan triggert weiterhin nicht (Beispiel: VPD 0.34 bei Min 0.7).

### Antwort
Ich habe den Direct-Shelly-Pfad für Abluft robuster gemacht: Auth-Fallback (mit/ohne Credentials) beim Lesen/Setzen sowie sauberes Abbrechen bei fehlgeschlagenem Set.

### Änderungen
- Abluft Direct-Read/Direct-Set versucht jetzt automatisch beide Varianten:
  - mit konfigurierten Credentials
  - ohne Auth (Fallback)
- Betrifft:
  - `_read_exhaust_shelly_output(...)`
  - `_get_exhaust_shelly_direct_state_from_payload(...)`
  - `_set_exhaust_shelly_output(...)`
- VPD-Regelung aktualisiert `exhaust_vpd_triggered` nur noch, wenn ein notwendiger Set-Vorgang auch wirklich erfolgreich war.
- Version auf `v0.94` erhöht.

## v0.93

### Frage
Abluft-Plan triggert nicht.

### Antwort
Ich habe den Direct-Read/Set-Pfad der Abluft um Auth-Unterstützung erweitert (gleiche Credentials wie Shelly Main), damit geschützte Shelly-Exhaust-Geräte zuverlässig gelesen/geschaltet werden.

### Änderungen
- Direkte Abluft-Shelly-Funktionen nehmen jetzt Tent-Kontext für Auth:
  - `_read_exhaust_shelly_output(payload, tent)`
  - `_get_exhaust_shelly_direct_state_from_payload(payload, tent)`
  - `_set_exhaust_shelly_output(payload, turn_on, tent)`
- Bei direkten Exhaust-Reads/Sets wird optional Basic Auth genutzt (`shelly_main_user/password`).
- VPD-Automation verwendet diesen Auth-fähigen Direct-Pfad.
- Endpoint `GET /tents/{tent_id}/shelly/exhaust/direct` nutzt ebenfalls Auth-fähigen Direktread.
- Version auf `v0.93` erhöht.

## v0.92

### Frage
Istzustand der Abluft bitte direkt vom Shelly nehmen (wie Hauptschalter), nicht von `/api/state`, da zu langsam.

### Antwort
Ich habe die Abluft-Zustandsermittlung vollständig auf direkte Shelly-Reads umgestellt (kein `/api/state`-Fallback für den Istzustand).

### Änderungen
- Regelung `_try_run_exhaust_vpd_control(...)`:
  - nutzt Istzustand ausschließlich via direktem Shelly-Read
  - bei Read-Fehler keine Umschalt-Aktion (statt Payload-Fallback)
- Neuer Endpoint:
  - `GET /tents/{tent_id}/shelly/exhaust/direct`
  - liefert direkten Shelly-Status (`isOn`, `Watt`, `Wh`) + `checked_at`
- Dashboard `loadLatest()`:
  - überschreibt Abluft-Status aus `/api/state` mit direktem Shelly-Status
- Version auf `v0.92` erhöht.

## v0.91

### Frage
Abluft wird falsch getriggert (an/aus trotz noch nicht erreichtem Min-VPD).

### Antwort
Ich habe die Regelung stabilisiert: statt blindem Toggle wird jetzt der reale Shelly-Zustand direkt gelesen und explizit auf Sollzustand gesetzt.

### Änderungen
- Neue Direct-Shelly-Helfer für Abluft:
  - `_read_exhaust_shelly_output(payload)`
  - `_set_exhaust_shelly_output(payload, turn_on)`
- Steuerung umgestellt von Toggle auf explizites Setzen:
  - Gen2: `Switch.Set`
  - Gen1: `/relay/0?turn=on|off`
- Regelung nutzt jetzt den **direkt gelesenen Ist-Zustand** (Fallback auf Payload nur bei Read-Fehler).
- Dadurch kein Flip-Flop mehr durch veraltete Payload-Werte zwischen Poll-Zyklen.
- Version auf `v0.91` erhöht.

## v0.90

### Frage
Bitte Hysterese für die neue Abluft-VPD-Steuerung ergänzen.

### Antwort
Ich habe eine konfigurierbare Hysterese ergänzt und die Schaltlogik darauf umgestellt.

### Änderungen
- Abluft-VPD-Plan erweitert um `hysteresis_kpa` (Default `0.05`).
- API erweitert:
  - `GET /tents/{tent_id}/exhaust-vpd-plan` liefert jetzt auch `hysteresis_kpa`.
  - `PUT /tents/{tent_id}/exhaust-vpd-plan` akzeptiert/speichert `hysteresis_kpa`.
- Dashboard-Modal erweitert um Feld **Hysterese (kPa)**.
- Poller-Logik mit Hysterese:
  - Einschalten bei `VPD < min_vpd_kpa`
  - Ausschalten erst bei `VPD >= min_vpd_kpa + hysteresis_kpa`
- DE/EN Übersetzungen für Hysterese ergänzt.
- Version auf `v0.90` erhöht.

## v0.89

### Frage
Abluft bitte direkt nach Min-VPD steuern: AN wenn VPD unter Min, AUS wenn VPD über/gleich Min (ähnlich Hauptschalter-Logik).

### Antwort
Die Abluft-Automation wurde auf direkte Schwellenwert-Steuerung umgestellt.

### Änderungen
- `_try_run_exhaust_vpd_control(...)` angepasst:
  - berechnet Soll-Zustand aus Schwelle (`should_be_on = vpd < min_vpd_kpa`)
  - wenn Ist != Soll → `POST /shelly/exhaust/toggle`
  - wenn Ist == Soll → keine Aktion
- Damit gilt jetzt explizit:
  - **VPD < Min** → Abluft **AN**
  - **VPD >= Min** → Abluft **AUS**
- Trigger-Status wird weiterhin in `exhaust_vpd_triggered` konsistent mit Sollzustand gepflegt.
- Version auf `v0.89` erhöht.

## v0.88

### Frage
Wenn eine Abluft-IP definiert ist, soll bei massiv zu niedrigem VPD automatisch geschaltet werden. Zusätzlich konfigurierbar/deaktivierbar im Backend (ähnlich Bewässerungsplan), inkl. Min-VPD-Schwelle. Button in Growphase-Kachel neben „Zähler zurücksetzen“.

### Antwort
Ich habe einen neuen Abluft-VPD-Plan ergänzt (pro Zelt), inkl. Modal in der Growphase-Kachel und Poller-Automation mit Trigger-Logik.

### Änderungen
- DB / Datenmodell erweitert:
  - `exhaust_vpd_plan_json` (Default: `{"enabled":false,"min_vpd_kpa":0.6}`)
  - `exhaust_vpd_triggered` (Re-Arm/Flatter-Schutz)
- Neue API-Endpunkte:
  - `GET /tents/{tent_id}/exhaust-vpd-plan`
  - `PUT /tents/{tent_id}/exhaust-vpd-plan`
- Poller-Automation ergänzt:
  - `_try_run_exhaust_vpd_control(tent, payload)`
  - läuft nur wenn Plan aktiv und `settings.shelly.exhaust.ip` gesetzt
  - wenn `vpdKpa < min_vpd_kpa` und noch nicht ausgelöst + Abluft aus → `POST /shelly/exhaust/toggle`
  - Re-Arm bei Erholung (`vpd >= min_vpd_kpa`)
- Dashboard UI:
  - Neuer Button in Growphase-Actions neben „Zähler zurücksetzen“: **Abluft-VPD-Plan**
  - Neues Modal mit:
    - Aktiv-Schalter
    - Min. VPD (kPa)
    - Speichern/Abbrechen
  - DE/EN Übersetzungen ergänzt.
- Version auf `v0.88` erhöht.

## v0.87

### Frage
Bitte ergänzen, dass das Backend für ESP32 Relay Boards das Repo `https://github.com/syschelle/GrowTent` voraussetzt.

### Antwort
Ich habe die Permanente Systembeschreibung um eine eigene Firmware-Voraussetzungsrubrik ergänzt.

### Änderungen
- Neue Rubrik unter **Systemanforderungen**:
  - **Firmware-Voraussetzung (ESP32 Relay Boards)**
- Klar dokumentiert:
  - Abhängigkeit vom Repo `https://github.com/syschelle/GrowTent`
  - Erwartete API-/Payload-Kompatibilität
  - Folgen bei nicht kompatibler Firmware
- Version auf `v0.87` erhöht.

## v0.86

### Frage
Bitte die Permanente Systembeschreibung aktualisieren (Projektziel + Systemanforderungen), da viele neue Funktionen dazugekommen sind.

### Antwort
Ich habe die Permanente Systembeschreibung inhaltlich aktualisiert und um eine klare Rubrik „Systemanforderungen“ ergänzt.

### Änderungen
- Projektziel auf den aktuellen Umfang erweitert (Shelly direkt, Energiehistorie, 2FA, Bewässerungsplanung, mobile DE/EN-UI).
- Technische Umsetzung auf aktuellen Stand gebracht.
- Neue Rubrik **Kernfunktionen** ergänzt.
- Neue Rubrik **Systemanforderungen** ergänzt:
  - Runtime/Netzwerk
  - Ports
  - Software/Stack
  - Persistenz/Betrieb
- Version auf `v0.86` erhöht.

## v0.85

### Frage
Bitte rechts zusätzlich die Einheit anzeigen und denselben Platz wie links verwenden.

### Antwort
Ich habe die rechte Y-Achse mit Einheit ergänzt und links/rechts auf dieselbe feste Achsenbreite gebracht.

### Änderungen
- Rechte Y-Achse zeigt jetzt ebenfalls den Unit-Text (z. B. `°C`, `%`, `kPa`, `W`).
- Linke und rechte Y-Achse haben identische feste Breite (`afterFit -> 56px`) für symmetrischen Platz.
- Anpassung in allen betroffenen Charts (Single-Chart-Builder + Temp/VPD-Spezialcharts).
- Version auf `v0.85` erhöht.

## v0.84

### Frage
Wertebereich in den Histogrammen zusätzlich auf der rechten Seite anzeigen.

### Antwort
Ich habe die Verlaufscharts so erweitert, dass die Y-Achse jetzt links und rechts sichtbar ist.

### Änderungen
- Alle betroffenen Charts zeigen nun zusätzlich eine rechte Y-Achse (`yR`) mit Ticks.
- Grid bleibt nur von links aktiv (`yR` zeichnet kein Grid ins Chart), damit es sauber bleibt.
- Temp- und VPD-Chart angepasst (inkl. Ziel-Linie weiterhin auf linker Hauptachse).
- Allgemeiner Single-Chart-Builder (Humidity, ExtTemp, Main Consumption) ebenfalls auf linke+rechte Achse erweitert.
- Legende filtert technische Hilfs-Datasets aus.
- Version auf `v0.84` erhöht.

## v0.83

### Frage
Nach Fix zeigte die Hauptschalter-Kachel teilweise weiterhin `Update -`.

### Antwort
Ich habe die Zeitstempel-Logik für den Main-Direktread stabilisiert, damit kein unnötiges Zurückfallen auf `-` passiert.

### Änderungen
- `GET /tents/{tent_id}/shelly/main/direct` liefert jetzt zusätzlich `checked_at` (UTC ISO-Zeit).
- Frontend nutzt für Main-Kachel bevorzugt `checked_at` als Aktualisierungszeitpunkt.
- Entferntes Verhalten: Zeitstempel wird nicht mehr auf `null` gesetzt, wenn ein einzelner Direkt-Read mal nicht `ok` liefert.
- Fallback ergänzt: wenn noch kein Main-Direktzeitstempel vorhanden ist, wird initial `captured_at` der Latest-Response genutzt.
- Version auf `v0.83` erhöht.

## v0.82

### Frage
Die Hauptschalter-Kachel zeigt als letzte Aktualisierung z. B. "vor 18 Stunden".

### Antwort
Für die Main-Shelly-Kachel nutze ich jetzt bei erfolgreichem Direkt-Read einen frischen Zeitstempel (direkter Pollzeitpunkt), damit die Anzeige nicht mehr mit einem alten letzten Schaltwechsel verwechselt wird.

### Änderungen
- Frontend-Statuszeit für Shelly `main` angepasst:
  - bei erfolgreichem `GET /tents/{id}/shelly/main/direct` wird `shellyMainDirectTs = now` gesetzt
  - Kachel zeigt für `main` diesen Aktualisierungszeitpunkt statt reinem letzten Switch-Event
- Fallback bleibt: wenn direkter Read fehlschlägt, wird wieder der bisherige Switch-Zeitstempel genutzt.
- Version auf `v0.82` erhöht.

## v0.81

### Frage
Hauptschalter aktualisiert nach Eingabe von Benutzer/Passwort nicht.

### Antwort
Ich habe die direkte Main-Shelly-Verbindung robuster gemacht: Wenn die aktuellen Shelly-Main-Parameter nicht im letzten Cache stehen, holt das Backend sie einmal live vom Controller (`/api/state`) und speichert sie, bevor es den direkten Shelly-Read ausführt.

### Änderungen
- `_extract_main_shelly_conn()` erweitert um Fallback:
  - live Controller-Read bei fehlender `settings.shelly.main.ip`
  - Persistenz via `save_state(...)`
  - danach erneute IP/Gen-Ermittlung
- Fehlermeldung präzisiert bei fehlender Main-IP.
- Version auf `v0.81` erhöht.

## v0.80

### Frage
Die History für `Gesamtverbrauch` soll ab jetzt vom Shelly direkt kommen, nicht mehr vom ESP32-Payload.

### Antwort
Ich habe den Poller so angepasst, dass vor dem Speichern in `tent_state` die Main-Shelly-Werte (`Watt`/`Wh`) direkt am Shelly abgefragt und ins Payload geschrieben werden.

### Änderungen
- Neue Poller-Hilfsfunktion: `_refresh_main_shelly_in_payload(payload, tent)`
  - liest `settings.shelly.main.ip` + `gen`
  - verwendet pro-Zelt `shelly_main_user` / `shelly_main_password` (optional)
  - holt `Watt`/`Wh` direkt von Shelly (Gen1/Gen2)
  - schreibt in `cur.shelly.main.Watt` und `cur.shelly.main.Wh`
- `poll_loop()` ruft die direkte Shelly-Aktualisierung vor `save_state()` auf.
- Dadurch basiert die Verlaufskurve `Gesamtverbrauch` ab jetzt auf Shelly-Daten.
- Version auf `v0.80` erhöht.

## v0.79

### Frage
`Wh` bitte in `kWh` umrechnen.

### Antwort
Ich habe die direkte Main-Shelly-Statusantwort um einen bereits umgerechneten `kWh`-Wert ergänzt.

### Änderungen
- Endpoint `GET /tents/{tent_id}/shelly/main/direct` liefert jetzt zusätzlich:
  - `kWh` (aus `Wh / 1000`)
- `Wh` bleibt aus Kompatibilitätsgründen erhalten.
- Version auf `v0.79` erhöht.

## v0.78

### Frage
Hauptschalter soll im Backend direkt steuerbar sein (toggle + Watt/Wh-Status), inklusive Setup-Felder für Shelly Main User/Passwort pro Zelt; Entkopplung vom reinen `/api/state`-Toggle.

### Antwort
Ich habe den Main-Shelly im Backend auf direkte Steuerung/Lesung umgestellt und die Credentials pro Zelt im Setup ergänzt.

### Änderungen
- Datenmodell `tents` erweitert:
  - `shelly_main_user`
  - `shelly_main_password`
- Setup/Tents-Form erweitert um:
  - `Shelly Main User`
  - `Shelly Main Password`
  - Werte werden bei Add/Edit gespeichert.
- Neue direkte Main-Shelly-Read-API:
  - `GET /tents/{tent_id}/shelly/main/direct`
  - liest Gen1/Gen2 direkt am Shelly (mit optional Basic Auth)
  - liefert `isOn`, `Watt`, `Wh`.
- Toggle-Route erweitert:
  - `POST /tents/{tent_id}/actions/shelly/main/toggle` läuft jetzt direkt gegen Shelly (Gen1/Gen2), nicht via Controller-Proxy.
- Dashboard:
  - Main-Werte (`isOn/Watt/Wh`) werden in `loadLatest()` direkt über die neue API geholt und auf die Card gemappt.
  - Main-Card ist jetzt auch toggelbar.
- Version auf `v0.78` erhöht.

## v0.77

### Frage
`Zeitraum` im Setup soll in `Zeitraum Historie` geändert werden (inkl. Übersetzung).

### Antwort
Ich habe das Setup-Label angepasst.

### Änderungen
- Setup-i18n `range` geändert:
  - DE: `Zeitraum Historie`
  - EN: `History range`
- Version auf `v0.77` erhöht.

## v0.76

### Frage
Setup-Seite wirkt in einer Spalte zusammengequetscht; soll responsiver und moderner wirken.

### Antwort
Ich habe das Setup-Layout auf ein responsives Card-Grid umgestellt, mit besserer Verteilung auf breiten Displays und sauberem 1-Spalten-Fallback auf Mobile.

### Änderungen
- Setup-`main` auf `setup-content` Grid umgestellt (`auto-fit`, min 320px).
- Setup-Überschrift über volle Breite.
- Alle Setup-Cards dürfen volle Grid-Breite nutzen (`max-width`-Override).
- Zelte-Card gezielt über beide Spalten (`#setupTentsCard`).
- Mobile Breakpoint ergänzt: unter 780px wieder eine Spalte.
- Version auf `v0.76` erhöht.

## v0.75

### Frage
Anmeldemaske inkl. 2FA wird nur im dunklen Theme angezeigt.

### Antwort
Ich habe die Login-/2FA-Seite auf Theme-Variablen umgestellt und das gespeicherte UI-Theme (`gt_theme`) übernommen.

### Änderungen
- `/auth/login` Styling auf Dark/Light per CSS-Variablen erweitert.
- Login-Card, Inputs und Buttons passen sich jetzt an das Theme an.
- Beim Laden wird `localStorage.gt_theme` gelesen und auf `documentElement` gesetzt.
- Betrifft beide Schritte: Username/Passwort und 2FA.
- Version auf `v0.75` erhöht.

## v0.74

### Frage
Im hellen Theme ist die obere Chart-Legende (z. B. Temperatur / Sollwert) schwer lesbar.

### Antwort
Ich habe die Legenden-Schriftfarbe der Charts theme-abhängig gemacht, damit sie im Light Theme klar dunkel dargestellt wird.

### Änderungen
- Neue Helper-Funktion: `chartLegendColor()`
  - Light: `#0f172a`
  - Dark: `#e2e8f0`
- Legendenfarbe in allen relevanten Charts auf `chartLegendColor()` umgestellt:
  - Standard-Chartbuilder
  - Temperatur-Chart (mit Soll-Linie)
  - VPD-Chart (mit Soll-Linie)
- Version auf `v0.74` erhöht.

## v0.73

### Frage
Helles Theme leicht gräulicher machen, dabei Sollwert-Linien in den Histories weiterhin klar erkennbar halten.

### Antwort
Ich habe das Light Theme dezent gräulicher gestaltet und die Sollwert-Linien kontraststärker für Light Mode gemacht.

### Änderungen
- Light Theme Farben angepasst (Setup/App/Changelog/App-Shell):
  - `--bg`: `#eef2f5`
  - `--card`: `#f8fafc`
  - `--grid`: leicht stärker
- Sollwert-Linien (Temperatur/VPD) jetzt mit theme-abhängiger Farbe:
  - Dark: `#94a3b8`
  - Light: `#64748b` (besser sichtbar)
- Version auf `v0.73` erhöht.

## v0.72

### Frage
`Vorschau öffnen` soll zu `Vollbild öffnen` geändert werden, inkl. Übersetzung.

### Antwort
Ich habe die Button-Beschriftung im Dashboard auf Vollbild umbenannt und die Übersetzung aktualisiert.

### Änderungen
- i18n-Key `openPreview` angepasst:
  - DE: `Vollbild öffnen`
  - EN: `Open fullscreen`
- Version auf `v0.72` erhöht.

## v0.71

### Frage
Im Vorschau-Fenster soll oben ein `Schließen`-Button angezeigt werden.

### Antwort
Ich habe im Header des Vorschau-Fensters einen gut sichtbaren `Schließen`-Button ergänzt.

### Änderungen
- Vorschau-Header erweitert um rechten Actions-Bereich:
  - Live-Update-Zeit
  - `Schließen`-Button (`window.close()`)
- Version auf `v0.71` erhöht.

## v0.70

### Frage
`Vorschau öffnen` soll im Stil des Backends cooler/designt sein.

### Antwort
Ich habe das externe Vorschaufenster optisch an den CanopyOps-Backendstil angepasst.

### Änderungen
- Vorschau-Fenster neu gestaltet:
  - dunkler CanopyOps-Hintergrund
  - Header-Leiste im Kartenstil
  - Titel `CanopyOps · Vorschau`
  - rechts Live-Update-Zeitstempel
- Bildbereich bleibt groß und zentriert (`contain`) mit zyklischem Refresh (2.5s).
- Version auf `v0.70` erhöht.

## v0.69

### Frage
`Vorschau öffnen` zeigt weiterhin kein Bild.

### Antwort
Ursache war das Öffnen des Popup-Fensters mit `noopener,noreferrer`; dadurch konnte das Skript den Inhalt des neuen Fensters nicht zuverlässig initialisieren. Ich habe das für dieses interne Preview-Fenster entfernt.

### Änderungen
- `window.open` für `Vorschau öffnen` angepasst:
  - entfernt: `noopener,noreferrer`
  - behalten: Fenstergröße (`1200x800`)
- Damit wird das Bild im Extra-Fenster wieder angezeigt und zyklisch aktualisiert.
- Version auf `v0.69` erhöht.

## v0.68

### Frage
Preview im Dashboard und `Vorschau öffnen` aktualisieren nicht mehr.

### Antwort
Ich habe die Vorschau-Fensterlogik auf DOM-basiertes Rendering mit Timer umgestellt, damit die geöffnete Vorschau wieder zyklisch aktualisiert wird.

### Änderungen
- `Vorschau öffnen` nutzt wieder ein eigenes Fenster mit großem Bild und Refresh alle 2.5s.
- Keine fragile `document.write`-Script-Inline-Variante mehr.
- Dashboard-Preview-Refresh bleibt aktiv wie zuvor.
- Version auf `v0.68` erhöht.

## v0.67

### Frage
Das Vorschaufenster zeigt nichts an.

### Antwort
Ich habe den Vorschau-Öffner vereinfacht: statt einer per `document.write` erzeugten HTML-Seite wird jetzt direkt die Preview-URL in einem neuen Fenster geöffnet.

### Änderungen
- `streamOpenBtn` öffnet direkt `preview_url` (mit Zeitstempel-Parameter gegen Cache).
- Entfernt die fehleranfällige Inline-HTML/Script-Erzeugung im Popup.
- Version auf `v0.67` erhöht.

## v0.66

### Frage
Nach der letzten Änderung funktionieren Stream und Werte im Dashboard nicht mehr.

### Antwort
Ursache war ein HTML-Script-Parsing-Problem in der neuen Vorschau-Fenster-Logik (`</script>` innerhalb eines JS-Strings). Dadurch wurde das Dashboard-Skript vorzeitig beendet.

### Änderungen
- In der `window.open`-Preview-HTML-Template-Zeichenkette das schließende Script-Tag entschärft:
  - `</script>` -> `<\\/script>`
- Dadurch läuft das Dashboard-JavaScript wieder vollständig (Stream-Preview + Werte laden wieder).
- Version auf `v0.66` erhöht.

## v0.65

### Frage
`Player öffnen` soll ersetzt werden: statt Livestream eine größere Vorschau in einem Extra-Fenster anzeigen.

### Antwort
Ich habe den Player-Link im Dashboard auf einen Vorschau-Öffner umgestellt, der ein eigenes Fenster mit großer, automatisch aktualisierter JPEG-Preview öffnet.

### Änderungen
- Button-Label geändert:
  - EN: `Open preview`
  - DE: `Vorschau öffnen`
- `streamOpenBtn` öffnet jetzt ein separates Fenster mit großem Preview-Bild statt Player/Live-Stream.
- Extra-Fenster aktualisiert das Bild weiterhin zyklisch (2.5s), wie die Dashboard-Preview.
- Anzeige ist jetzt primär an verfügbare `preview_url` gebunden.
- Version auf `v0.65` erhöht.

## v0.64

### Frage
Bewässerungsplan-Button ist nicht sichtbar; er soll in der Dashboard-Bewässerungskachel rechts neben `Bewässerung starten` erscheinen und nur bei 8x-Boards sichtbar sein.

### Antwort
Ich habe den Bewässerungsplan direkt in die Bewässerungs-Aktionszeile der Dashboard-Kachel integriert und ein eigenes Plan-Modal im Dashboard ergänzt.

### Änderungen
- Dashboard Bewässerungs-Aktionen (nur bei 8x):
  - `Start watering`
  - `Irrigation plan` (neu, gleiche Zeile)
- Neues Dashboard-Modal `dbIrPlanModal`:
  - Aktiv
  - Alle N Tage
  - Minuten nach Licht an
  - Laden/Speichern über:
    - `GET /tents/{id}/irrigation-plan`
    - `PUT /tents/{id}/irrigation-plan`
- i18n im Dashboard ergänzt (DE/EN):
  - `irrigationPlan`, `everyDays`, `offsetAfterLight`, `savePlan`, `cancel`, `active`
- Version auf `v0.64` erhöht.

## v0.63

### Frage
Bewässerungsplan als eigenes Fenster pro Zelt integrieren (alle N Tage + Minuten nach Licht an).

### Antwort
Ich habe einen eigenen Bewässerungsplan-Dialog pro Zelt ergänzt und einen Backend-Scheduler eingebaut, der den Plan automatisch ausführt.

### Änderungen
- Datenmodell/DB erweitert (`tents`):
  - `irrigation_plan_json`
  - `irrigation_last_run_date`
- Neue API-Endpunkte:
  - `GET /tents/{tent_id}/irrigation-plan`
  - `PUT /tents/{tent_id}/irrigation-plan`
- Setup-UI:
  - Pro Zelt Button `Bewässerungsplan / Irrigation plan`
  - eigenes Modal mit Feldern:
    - Aktiv
    - Alle N Tage
    - Minuten nach Licht an
- Poller/Scheduler:
  - prüft 8x-Board + nicht bereits laufende Bewässerung
  - liest Licht-ON-Zeit aus `settings.shelly.light.line`
  - triggert Bewässerung via Controller `POST /startWatering`
  - schützt vor Doppelausführung per `irrigation_last_run_date` + N-Tage-Intervall
- Version auf `v0.63` erhöht.

## v0.62

### Frage
Sollwert-Linien im Temperatur-/VPD-Verlauf sind in der Backend-App nicht sichtbar.

### Antwort
Ich habe die Sollwert-Ermittlung robuster gemacht und zusätzliche Fallback-Keys ergänzt, damit die Linien auch bei abweichenden Payload-Varianten erscheinen.

### Änderungen
- Sollwert-Fallbacks ergänzt:
  - Temperatur: `settings.grow.targetTemperature` -> `settings.targetTemperature` -> `target.targetTempC`
  - VPD: `settings.grow.targetVPD` -> `settings.targetVPD` -> `target.targetVpdKpa`
- Zielwerte werden jetzt mit `firstNum(...)` robust ausgelesen und als Chart-Sollwertlinien genutzt.
- Version auf `v0.62` erhöht.

## v0.61

### Frage
Auf der ersten Login-Maske (Benutzername/Passwort) soll Enter den `Weiter`-Button auslösen.

### Antwort
Ich habe Enter-Handling für die Felder der ersten Login-Stufe ergänzt.

### Änderungen
- Login-Seite (`/auth/login`) erweitert:
  - `keydown`-Handler für `u` und `p`
  - bei `Enter`: `b1.click()` (Weiter)
- Bestehendes Enter-Handling für 2FA-Stufe bleibt unverändert.
- Version auf `v0.61` erhöht.

## v0.60

### Frage
Im Temperaturverlauf und VPD-Verlauf sollen die jeweiligen Sollwerte eingeblendet werden (in grau).

### Antwort
Ich habe in beiden Diagrammen eine zusätzliche graue Sollwert-Linie ergänzt.

### Änderungen
- Temperatur-Chart:
  - zusätzliche Dataset-Linie `Soll/Target` in Grau (`#94a3b8`, gestrichelt)
  - Wert aus `settings.grow.targetTemperature` (mit °C/°F-Umrechnung)
- VPD-Chart:
  - zusätzliche Dataset-Linie `Soll/Target` in Grau (`#94a3b8`, gestrichelt)
  - Wert aus `settings.grow.targetVPD`
- Zielwerte werden in `loadLatest()` übernommen und in `buildCharts()` verwendet.
- Version auf `v0.60` erhöht.

## v0.59

### Frage
`Sensorname + Temperatur` soll nicht in der Kachel der aktuellen Werte stehen.

### Antwort
Ich habe die Current-Value-Kachel zurück auf nur den Sensornamen gestellt. Der kombinierte Text bleibt nur im Verlauf/Chart.

### Änderungen
- Current extTemp-Kachel (`lblExtTemp`) zeigt wieder nur `sensors.cur.ds18b20Name`.
- Verlaufstitel und Dataset bleiben dynamisch als `Sensorname + Temperatur/Temperature`.
- Version auf `v0.59` erhöht.

## v0.58

### Frage
Beim `sensors.cur.extTempC`-Histogramm ist ein fester Name hinterlegt. Stattdessen soll der Sensorname verwendet werden und danach `Temperatur` (übersetzt).

### Antwort
Ich habe die extTemp-Beschriftungen dynamisch auf `Sensorname + Temperatur` umgestellt (inkl. Übersetzung), sowohl für die Karte als auch für den Verlaufstitel/Dataset-Label.

### Änderungen
- Neue Label-Hilfsfunktion im Frontend: `extTempLabelBase()` => `"<Sensorname> <temperature>"`.
- Dynamischer Sensorname aus `sensors.cur.ds18b20Name` wird in `extTempSensorName` gespeichert.
- Angepasst:
  - `lblExtTemp`
  - `lblExtTempHistory`
  - extTemp-Chart Dataset-Label
- `Temperatur/Temperature` nutzt i18n via bestehendem `tr('temperature')`.
- Version auf `v0.58` erhöht.

## v0.57

### Frage
In der Bewässerungs-Kachel soll hinter `Bewässerung` ein rotes `aktiv` erscheinen, wenn `Durchläufe übrig` größer als 0 ist.

### Antwort
Ich habe einen roten Aktiv-Status direkt neben dem Bewässerungs-Titel ergänzt und an `irrigation.runsLeft > 0` gebunden.

### Änderungen
- Titel der Bewässerungs-Kachel erweitert um `#irActiveBadge`.
- Badge-Logik in `loadLatest()`:
  - sichtbar bei `runsLeft > 0`
  - ausgeblendet bei `runsLeft <= 0` bzw. wenn keine 8x-Bewässerung aktiv ist.
- i18n ergänzt:
  - EN: `active`
  - DE: `aktiv`
- Version auf `v0.57` erhöht.

## v0.56

### Frage
Uptime-Anzeige ohne Rahmen und in derselben Schrift wie `Update vor 1 Min`.

### Antwort
Ich habe das Uptime-Badge auf reine `small`-Textdarstellung ohne Rahmen/Padding zurückgebaut.

### Änderungen
- `#uptimeBadge` Styling vereinfacht:
  - entfernt: Border, Radius, Padding
  - bleibt: `class="small"` wie die Update-Zeilen
- Version auf `v0.56` erhöht.

## v0.55

### Frage
`sys.uptimeS` aus den Stats/State-Daten auslesen und links neben `Open ESP` anzeigen, inklusive Umrechnung in genau eine passende Einheit (Sekunden oder Minuten oder Stunden oder Tage).

### Antwort
Ich habe eine Uptime-Anzeige in der Header-Actions-Zeile ergänzt (links neben `Open ESP`) und eine Single-Unit-Formatierung implementiert.

### Änderungen
- Neue Header-Anzeige: `#uptimeBadge` links neben `Open ESP`.
- Uptime aus `sys.uptimeS` gelesen.
- Neue Formatfunktion `formatUptimeSingleUnit(seconds)`:
  - >= 1 Tag -> `x Tg/d`
  - sonst >= 1 Stunde -> `x Std/h`
  - sonst >= 1 Minute -> `x Min/min`
  - sonst Sekunden -> `x Sek/s`
- i18n ergänzt:
  - `uptime`, `uptimeDay`, `uptimeHour`, `uptimeMinute`, `uptimeSecond` (DE/EN)
- Badge wird ausgeblendet, wenn kein valider Uptime-Wert vorliegt.
- Version auf `v0.55` erhöht.

## v0.54

### Frage
In der Bewässerung soll `Menge:` in `Menge pro Task:` geändert werden, inkl. Übersetzung.

### Antwort
Ich habe das Label in DE/EN angepasst.

### Änderungen
- i18n-Text `irAmount` geändert:
  - DE: `Menge pro Task`
  - EN: `Amount per task`
- Version auf `v0.54` erhöht.

## v0.53

### Frage
`Verbrauch heute (0-24)` soll in `Verbrauch / Kosten heute (0-24)` umbenannt werden, inkl. Übersetzung.

### Antwort
Ich habe das Label in DE und EN angepasst.

### Änderungen
- i18n-Text `consumptionToday` geändert:
  - DE: `Verbrauch / Kosten heute (0-24)`
  - EN: `Consumption / cost today (0-24)`
- Version auf `v0.53` erhöht.

## v0.52

### Frage
Bei `Verbrauch heute (0-24)` sollen hinter der kWh noch die aktuellen Tageskosten stehen, getrennt mit Schrägstrich.

### Antwort
Ich habe die Anzeige auf `kWh / €` erweitert und beide Werte aus den heutigen Verlaufsdaten (seit 0:00) berechnet.

### Änderungen
- History-Punkte erweitert um `mainCost` (`cur.shelly.main.Cost`).
- Tagesberechnung nutzt heute-Werte:
  - Energie: `mainWh(last) - mainWh(first)`
  - Kosten: `mainCost(last) - mainCost(first)`
- Anzeigeformat in der Growphase:
  - `X.XXX kWh / Y.YY €`
  - Fallback: `- kWh / - €`
- Version auf `v0.52` erhöht.

## v0.51

### Frage
Soll `Verbrauch heute (0-24)` wirklich live seit 0:00 berechnet werden?

### Antwort
Ja — und ich habe die Berechnung jetzt explizit so gemacht, dass sie immer Daten seit lokal 00:00 nutzt, unabhängig vom ausgewählten Chart-Zeitraum.

### Änderungen
- Tagesverbrauchsberechnung in `loadHistory()` angepasst:
  - ermittelt `minutesSinceMidnight`
  - lädt bei Bedarf eine separate History-Abfrage seit 00:00
  - berechnet daraus `mainWh(last) - mainWh(first)`
- Damit bleibt `Verbrauch heute (0-24)` korrekt/live, auch wenn im UI z. B. nur 60 Minuten ausgewählt sind.
- Version auf `v0.51` erhöht.

## v0.50

### Frage
`Gesamtkosten` und `Verbrauch heute (0-24)` tauschen, sodass die Kosten ganz unten stehen.

### Antwort
Ich habe die Reihenfolge in der Growphase-Rechtsspalte angepasst: erst Verbrauch heute, dann Gesamtkosten.

### Änderungen
- Reihenfolge in der Growphase-Kachel geändert:
  1. Energie
  2. Verbrauch heute (0-24)
  3. Gesamtkosten
- `Gesamtkosten` steht jetzt ganz unten.
- Version auf `v0.50` erhöht.

## v0.49

### Frage
Der neue Tagesverbrauch in der Growphase soll "so wie Energie" aufgebaut sein.

### Antwort
Ich habe den Tagesverbrauch auf dasselbe Label+Wert-Muster wie Energie/Gesamtkosten umgestellt.

### Änderungen
- Growphase rechte Spalte erweitert:
  - Neues Label `lblMainKwhToday`
  - Neuer Wert-Chip `mainKwhTodayValue`
- Entfernt die vorherige Darstellung als eigener Text-Chip in der linken Statistikspalte.
- i18n-Label `consumptionToday` wird jetzt als eigene Überschrift genutzt; Wert separat als `kWh` angezeigt.
- Version auf `v0.49` erhöht.

## v0.48

### Frage
In der Growphase-Kachel soll ein zusätzlicher Eintrag für den Tagesverbrauch in kWh erscheinen (0:00 bis 24:00).

### Antwort
Ich habe in der Growphase-Kachel einen neuen Tagesverbrauchseintrag ergänzt, der aus den Main-Wh-Historiewerten pro lokalem Kalendertag berechnet wird.

### Änderungen
- Growphase-Kachel erweitert um neuen Chip: `mainKwhToday`.
- History-API liefert zusätzlich `mainWh` (`cur.shelly.main.Wh`) pro Punkt.
- Frontend-Berechnung in `loadHistory()`:
  - Filter auf heutigen lokalen Tag
  - Verbrauch = letzter `mainWh` minus erster `mainWh`
  - Anzeige in kWh mit 3 Nachkommastellen
- i18n ergänzt:
  - EN: `Consumption today (0-24)`
  - DE: `Verbrauch heute (0-24)`
- Version auf `v0.48` erhöht.

## v0.47

### Frage
Zusätzlichen Graphen für den Hauptschalter mit Watt-Werten hinzufügen und als `Gesamtverbrauch` (inkl. Übersetzung) benennen.

### Antwort
Ich habe einen neuen Verlaufsgrafen für `cur.shelly.main.Watt` ergänzt und die Bezeichnung als `Gesamtverbrauch / Total consumption` mit i18n eingebaut.

### Änderungen
- Neue Chart-Kachel im Dashboard:
  - Label-ID: `lblMainWHistory`
  - Canvas-ID: `mainWChart`
- History-Datenquelle nutzt bestehendes Feld `mainW` aus `/tents/{id}/history`.
- Frontend-Charts erweitert:
  - neue Serie `mainW` mit Einheit `W`
  - eigener roter Graph (`#ef4444`)
- i18n ergänzt:
  - `totalConsumption`: EN `Total consumption`, DE `Gesamtverbrauch`
  - `totalConsumptionHistory`: EN `Total consumption history`, DE `Gesamtverbrauchsverlauf`
- Version auf `v0.47` erhöht.

## v0.46

### Frage
`AN/AUS` in der Licht-Kachel soll nicht fett dargestellt werden.

### Antwort
Ich habe die ON/OFF-Zeit-Anzeige rechts neben der Wattzahl auf normale Schriftstärke gestellt.

### Änderungen
- Style der rechten Licht-Schedule-Anzeige angepasst:
  - `font-weight: 400` statt vererbter fetter Value-Schrift
- Version auf `v0.46` erhöht.

## v0.45

### Frage
Bitte auch die ON/OFF-Anzeige in der Licht-Kachel übersetzen.

### Antwort
Ich habe die Anzeige sprachabhängig gemacht.

### Änderungen
- Neue i18n-Keys ergänzt:
  - EN: `scheduleOn=ON`, `scheduleOff=OFF`
  - DE: `scheduleOn=AN`, `scheduleOff=AUS`
- Licht-Kachel verwendet diese Übersetzungen jetzt in der ON/OFF-Zeitzeile (rechts neben Watt).
- Version auf `v0.45` erhöht.

## v0.44

### Frage
ON/OFF-Zeiten der Licht-Shelly-Kachel sollen nicht in eigener Zeile stehen, sondern in derselben Zeile wie die Wattzahl, rechts ausgerichtet.

### Antwort
Ich habe die Darstellung umgestellt: Watt links, ON/OFF rechts in derselben Wert-Zeile.

### Änderungen
- Entfernt: eigene ON/OFF-Zeile unterhalb des Headers.
- Neu: gemeinsame `value`-Zeile mit Flex-Layout (`space-between`):
  - links: Wattwert
  - rechts: `ON ... | OFF ...` (nur bei Licht)
- Version auf `v0.44` erhöht.

## v0.43

### Frage
Die Licht-Kachel soll die konfigurierten ON/OFF-Zeiten aus `settings.shelly.light.line` anzeigen (unter der Update/Status-Zeile).

### Antwort
Ich habe die ON/OFF-Zeiten in der Licht-Shelly-Kachel ergänzt und direkt unter der Update/Status-Zeile platziert.

### Änderungen
- Shelly-Normalisierung erweitert um `settings.shelly.<key>.line`.
- In der Shelly-Card-Renderlogik:
  - ON/OFF aus der `line` geparst (z. B. `ON 5:00 | OFF 17:00`)
  - Anzeige nur in der Licht-Kachel (`key === "light"`)
  - Position: direkt unter `Update ...` + `AN/AUS`.
- Version auf `v0.43` erhöht.

## v0.42

### Frage
In der Tank-Kachel fehlt oben rechts die Update-Anzeige.

### Antwort
Ich habe die Update-Zeile oben rechts in der Tank-Kachel ergänzt.

### Änderungen
- Tank-Kachel Header erweitert um `tankLastChange` (oben rechts).
- Anzeige wird in `loadLatest()` aus `captured_at` gesetzt (gleiches Relative-Time-Format wie bei den anderen Update-Zeilen).
- Fallback/Initialwert über i18n: `Update -`.
- Version auf `v0.42` erhöht.

## v0.41

### Frage
Nach dem letzten Fix sind die Current-Values-Kacheln unterschiedlich hoch.

### Antwort
Ich habe das Layout so angepasst, dass die Kachelhöhen wieder einheitlich bleiben, ohne dass die anderen Kacheln durch die Tank-Zusatzinfos größer werden.

### Änderungen
- `#currentValuesGrid`-Spezialregel entfernt, damit das Standard-Stretch-Verhalten wieder gleich hohe Kacheln erzeugt.
- Tank-Kachel-Feinlayout geändert:
  - `tankLevelSub` absolut unten links positioniert
  - `tankCurrentActions` (Ping-Button) absolut unten rechts positioniert
  - Tank-Kachel auf `position: relative` gesetzt
- Version auf `v0.41` erhöht.

## v0.40

### Frage
Durch die Distance-Zeile in der Tank-Kachel werden alle Kacheln in der Current-Values-Zeile höher. Das soll nicht passieren.

### Antwort
Ich habe das Current-Values-Grid auf nicht-stretchendes Layout umgestellt, damit nur die Tank-Kachel ihre zusätzliche Zeile nutzt und die anderen Kacheln ihre natürliche Höhe behalten.

### Änderungen
- Current-Values-Grid mit eigener ID versehen: `#currentValuesGrid`
- CSS ergänzt: `#currentValuesGrid { align-items: start; }`
  - verhindert das globale Höherziehen aller Kacheln in dieser Reihe
- Version auf `v0.40` erhöht.

## v0.39

### Frage
`Distance` soll in der Tank-Kachel unter dem Prozentwert stehen, nicht oben rechts daneben.

### Antwort
Ich habe die Distance-Zeile aus dem Header unter den Prozentwert verschoben.

### Änderungen
- Tank-Kachel-Layout angepasst:
  - `tankLevelSub` nicht mehr im Header rechts
  - jetzt als eigene `small`-Zeile direkt unter `tankPercent`
- Version auf `v0.39` erhöht.

## v0.38

### Frage
`Ping Tank`-Button soll in die neue Tank-Kachel (Current Values) verschoben werden, rechts unten statt in der Bewässerungs-Aktionszeile.

### Antwort
Ich habe den Button aus der Bewässerungs-Kachel entfernt und in die Tank-Kachel verschoben, rechts unten ausgerichtet.

### Änderungen
- Neue Actions-Zeile in der Tank-Current-Kachel: `#tankCurrentActions`
  - Layout: rechtsbündig (`justify-content:flex-end`)
- `Ping tank` wird bei 8x-Boards jetzt dort gerendert.
- In der Bewässerungs-Kachel bleibt nur noch `Start watering`.
- Version auf `v0.38` erhöht.

## v0.37

### Frage
Zwischen den Current-Werten und den Relays ist ein sichtbar größerer Spalt als in den anderen Zeilen.

### Antwort
Ich habe den Abstand vor der Relays-Zeile reduziert, damit der vertikale Rhythmus wieder konsistent wirkt.

### Änderungen
- Relays-Karte mit kompakterem oberen Abstand versehen (`margin-top: 0`).
- Spalt zwischen Current-Grid und Relays visuell an die übrigen Zeilen angeglichen.
- Version auf `v0.37` erhöht.

## v0.37

### Frage
Tankwerte sollen im Backend-Dashboard unter den aktuellen Werten als eigene Kachel angezeigt werden – aber nur bei 8x-Relayboards.

### Antwort
Ich habe eine neue Tank-Kachel im Current-Values-Bereich ergänzt und sie strikt auf 8x-Relaykonfiguration begrenzt.

### Änderungen
- Neue Dashboard-Kachel im Current-Values-Grid:
  - Titel: `Tank level / Tankfüllstand`
  - Hauptwert: `irrigation.tankLevelPercent`
  - Unterzeile: `Distance / Abstand` mit `irrigation.tankLevelCm`
- Anzeige nur bei 8x-Boards:
  - gesteuert über `settings.active_relay_count === 8`
  - bei 4x wird die Kachel ausgeblendet
- i18n ergänzt:
  - `tankLevel` (EN/DE)
  - `tankDistance` (EN/DE)
- Version auf `v0.37` erhöht.

## v0.36

### Frage
`Zähler zurücksetzen` soll nur nach einer expliziten Sicherheitsabfrage (Alert/Confirm) ausgelöst werden.

### Antwort
Ich habe vor dem Auslösen des Reset-Requests ein Bestätigungsfenster eingebaut.

### Änderungen
- Growphase-Button `Reset counter / Zähler zurücksetzen` zeigt jetzt vor Ausführung ein `confirm()`-Dialogfenster.
- Bei Abbruch wird kein Request gesendet.
- Neue i18n-Texte:
  - EN: `Really reset energy counters?`
  - DE: `Energiezähler wirklich zurücksetzen?`
- Version auf `v0.36` erhöht.

## v0.35

### Frage
In der Growphase-Kachel soll der Button `Reset Counter` auf den Connector `/api/shelly/reset-energy` zeigen (inkl. Übersetzung).

### Antwort
Ich habe einen eigenen Backend-Action-Endpoint für den Reset ergänzt und den Button in der Growphase-Kachel daran angebunden.

### Änderungen
- Neuer Backend-Endpoint:
  - `POST /tents/{tent_id}/actions/shelly/reset-energy`
  - mapped auf Controller-Connector: `/api/shelly/reset-energy`
- Growphase-Kachel:
  - Button wird in `phaseActions` gerendert und ruft Reset-Action auf.
- i18n für Button:
  - EN: `Reset counter`
  - DE: `Zähler zurücksetzen`
- Version auf `v0.35` erhöht.

## v0.34

### Frage
Im `/api/state` gibt es neue Shelly-Geräte. Wenn bei Shellys eine IP gesetzt ist, sollen sie automatisch im Dashboard (pro Zelt) angezeigt werden.

### Antwort
Ich habe die Shelly-Anzeige dynamisch erweitert: Alle Geräte mit `settings.shelly.<name>.ip` werden jetzt automatisch als Karte gerendert.

### Änderungen
- Shelly-Karten dynamisch:
  - zusätzliche Geräte werden aus Payload-Keys (`settings.shelly.<name>.ip`) erkannt
  - nur Geräte mit gesetzter IP werden angezeigt
- Neues Standardgerät ergänzt: `exhaust` (Abluft)
  - EN/DE Übersetzung + Icon ergänzt
- Toggle erweitert:
  - Backend erlaubt jetzt auch `exhaust` in `/actions/shelly/{device}/toggle`
  - Frontend erlaubt Toggle für `exhaust`
- Shelly Last-Change Endpoint erweitert um `exhaust`.
- Version auf `v0.34` erhöht.

## v0.33

### Frage
In der Bewässerung soll `Gesamtmenge` in `Menge pro Topf` umbenannt werden (mit korrekter Übersetzung).

### Antwort
Ich habe das Label in DE/EN angepasst.

### Änderungen
- i18n Bewässerung angepasst:
  - DE: `Menge pro Topf`
  - EN: `Amount per pot`
- Version auf `v0.33` erhöht.

## v0.32

### Frage
Bei allen Buttons soll der Innenabstand zum Rand kleiner sein (weniger Spacing).

### Antwort
Ich habe die Button-Paddings global reduziert, damit alle Buttons kompakter wirken.

### Änderungen
- Kompaktere Button-Abstände in der UI:
  - globale `button`-Padding reduziert
  - `.stream-open-btn` Padding reduziert
  - `.header-btn` (inkl. Logout/View-Umschalter) Padding reduziert
  - `.menu-btn` und `.mobile-nav-toggle` Padding reduziert
  - `.relay` Button-Padding reduziert
- Einheitlicherer, dichterer Button-Look auf Desktop und Mobile.
- Version auf `v0.32` erhöht.

## v0.31

### Frage
Es werden keine Verläufe mehr angezeigt. Bitte prüfen und robuster machen.

### Antwort
Ich habe den Verlaufslader robuster gemacht und einen automatischen Fallback eingebaut, wenn im gewählten Zeitraum keine Daten vorhanden sind.

### Änderungen
- `loadHistory()` robuster gemacht:
  - Fehlerprüfung für History-Requests (`!r.ok`)
  - Fallback von gewähltem Zeitraum auf `10080` Minuten (7 Tage), wenn keine Punkte gefunden werden.
- UI-Rückmeldungen ergänzt:
  - Hinweis bei Fallback auf „letzte verfügbare Daten“
  - klare Meldung, wenn gar keine Verlaufsdaten vorhanden sind.
- Charts werden bei leeren Daten kontrolliert mit leeren Reihen gerendert statt still zu scheitern.
- Version auf `v0.31` erhöht.

## v0.30

### Frage
Der Umschalter „Mobile/Desktop Ansicht“ soll in den Header (mit Abstand zu Logout). Zusätzlich soll Logout den gleichen Stil wie die anderen Buttons bekommen.

### Antwort
Ich habe den View-Umschalter in den App-Header verschoben und den Logout-Button visuell an die übrigen Buttons angeglichen.

### Änderungen
- App-Shell Header erweitert:
  - neuer Button `Mobile Ansicht / Desktop Ansicht` im Header, mit Abstand vor Logout.
  - Umschalter schreibt `gt_view_mode` in `localStorage` und lädt den iframe-Inhalt neu.
- Logout-Button auf einheitlichen Button-Stil (`.header-btn`) umgestellt.
- View-Button aus der Dashboard-Titelzeile entfernt (jetzt zentral im Header).
- Version auf `v0.30` erhöht.

## v0.29

### Frage
Kann das Hamburger-Menü auch auf der Desktop-Seite genauso verwendet werden wie mobil?

### Antwort
Ja. Ich habe die App-Shell auf allen Geräten auf das gleiche Hamburger-Menü-Konzept umgestellt.

### Änderungen
- Sidebar in der App-Shell ist jetzt generell ein ausklappbares Overlay-Menü.
- Hamburger-Button (`☰`) ist nun auch auf Desktop aktiv.
- Einheitliches Verhalten Desktop + Mobile:
  - Klick auf `☰` öffnet/schließt Navigation
  - nach Navigation schließt das Menü wieder
- Desktop/Mobile verwenden damit denselben Navigations-Workflow.
- Version auf `v0.29` erhöht.

## v0.28

### Frage
In der mobilen Ansicht ist die Navigation noch zu groß. Gewünscht: echtes Hamburger-Menü im Header vor dem Logo/CanopyOps.

### Antwort
Ich habe die App-Shell auf ein Header-Hamburger-Menü umgestellt. Auf Mobilgeräten ist die Sidebar jetzt standardmäßig versteckt und per Menü-Button ein-/ausklappbar.

### Änderungen
- Neuer Header-Button `☰` (Hamburger) vor Logo/CanopyOps.
- Mobile Verhalten (`<=1024px`):
  - Sidebar initial versteckt
  - als Overlay unter dem Header einblendbar (`.sidebar.open`)
  - Auto-Schließen nach Navigation
- Spart deutlich vertikalen Platz in der mobilen Ansicht.
- Version auf `v0.28` erhöht.

## v0.27

### Frage
In der mobilen Ansicht ist die obere Navigationsleiste zu groß. Sie soll optimiert und auf-/zuklappbar sein.

### Antwort
Ich habe die mobile Sidebar auf ein kompaktes, aufklappbares Menü umgestellt.

### Änderungen
- Mobile Navigation optimiert:
  - Standardmäßig kompakt (geringe Höhe)
  - Auf-/Zuklappen per `Menü`-Button
  - Button wechselt zu `Schließen`
- Funktioniert sowohl bei schmalem Viewport als auch in erzwungener Mobile-Ansicht.
- Sidebar nimmt dadurch deutlich weniger vertikalen Platz ein.
- Version auf `v0.27` erhöht.

## v0.26

### Frage
Die neue Stream-Preview in der Übersicht lädt nicht.

### Antwort
Die Preview-Quelle war falsch auf einen nicht verfügbaren Stream-Alias gesetzt. Ich habe die Preview auf die direkte RTSP-Quelle umgestellt (wie beim Player), damit sie zuverlässig lädt.

### Änderungen
- `preview_url` in `/tents/{id}/latest` korrigiert:
  - vorher: `src=tent_{id}`
  - jetzt: `src=<rtsp_url>#media=video` (URL-encoded)
- Dadurch funktioniert die JPEG-Preview auch ohne registrierten `tent_{id}`-Alias in go2rtc.
- Version auf `v0.26` erhöht.

## v0.25

### Frage
Auf Mobilgeräten funktioniert Streaming schlecht. In der Übersicht soll die Framerate stark reduziert sein; voller Stream nur bei "Player öffnen".

### Antwort
Ich habe die Dashboard-Streamanzeige auf ein leichtgewichtiges JPEG-Live-Preview umgestellt und den Vollstream ausschließlich auf den Open-Player-Link begrenzt.

### Änderungen
- `/tents/{id}/latest` liefert zusätzlich `preview_url` (`/api/frame.jpeg?src=tent_{id}`).
- Dashboard-Streamkarte:
  - statt dauerhaftem iframe-Stream jetzt periodisch aktualisiertes JPEG-Preview (ca. alle 2.5s)
  - deutlich geringere Last/Bandbreite in der Übersicht
- Voller Stream bleibt erhalten, aber nur via Button **Player öffnen**.
- Verbesserung besonders für mobile Geräte mit schwächerer Verbindung/CPU.
- Version auf `v0.25` erhöht.

## v0.24

### Frage
- Es soll eine bessere Telefon-Ansicht geben, inkl. Umschalter zwischen Desktop/Mobile.
- Bei der 2FA-Eingabe soll der Cursor automatisch im 2FA-Feld stehen.

### Antwort
Ich habe einen View-Mode-Umschalter ergänzt (Desktop/Mobile) und den 2FA-Fokus im Login verbessert.

### Änderungen
- Dashboard: neuer View-Mode-Button in der Titelzeile.
  - Umschaltung zwischen erzwungener Mobile-Ansicht und Desktop-Ansicht.
  - Zustand wird in `localStorage` gespeichert (`gt_view_mode`).
- Mobile-Layout-Regeln ergänzt:
  - `body.force-mobile` erzwingt Telefon-Layout (Sidebar/Grids/Top-Cards kompakt).
- Login/2FA UX verbessert:
  - Nach Schritt 1 (requires2fa) wird Fokus automatisch auf das 2FA-Codefeld gesetzt.
  - Nach fehlgeschlagener 2FA-Prüfung springt Fokus ebenfalls zurück ins 2FA-Feld.
- Version auf `v0.24` erhöht.

## v0.23

### Frage
Oben beim Zeltnamen (Online/Offline-Zeile) soll ganz rechts ein Button zur ESP32-Webseite erscheinen – ohne `/api/state`.

### Antwort
Ich habe in der Titelzeile einen direkten ESP-Button ergänzt, der automatisch auf die Basis-URL des Controllers zeigt.

### Änderungen
- Neue Titelzeile mit rechtem Aktionsbutton:
  - EN: `Open ESP`
  - DE: `ESP öffnen`
- URL-Ableitung aus Tent-`source_url`:
  - aus `http://<ip>/api/state` wird `http://<ip>`
- Button wird nur angezeigt, wenn eine gültige Controller-URL vorhanden ist.
- Version auf `v0.23` erhöht.

## v0.22

### Frage
Alle Buttons sollen den gleichen modernen Stil haben. In den Shelly-Kacheln soll „Umschalten“ links unten und „Shelly öffnen“ rechts unten stehen.

### Antwort
Ich habe den Button-Stil vereinheitlicht und die Shelly-Aktionszeile exakt so angeordnet.

### Änderungen
- Globales Button-Styling vereinheitlicht (`button`):
  - gleicher Look (Radius, Gradient, Border, Hover/Active)
- Shelly-Karten-Layout angepasst:
  - `Umschalten` links unten
  - `Shelly öffnen` rechts unten
- Neue Utility-Klasse: `.shelly-actions` für stabile Bottom-Ausrichtung.
- Version auf `v0.22` erhöht.

## v0.21

### Frage
Kann der neue Shelly-Link optisch mehr wie ein Button aussehen (ähnlich andere Buttons), aber mit leicht anderer Farbe?

### Antwort
Ja. Ich habe den Shelly-Link als eigenen Button-Style gestaltet, passend zum bestehenden UI-Look mit dezent anderer Farbgebung.

### Änderungen
- Neuer UI-Style `.shelly-open-btn` für Shelly-Direktlinks.
- Optik: Button-ähnlich (Padding, Radius, Border, Gradient, Hover/Active-Effekt).
- Farbton leicht abgesetzt (cyan/blau), damit klar als Link-Aktion erkennbar.
- Version auf `v0.21` erhöht.

## v0.20

### Frage
Kann bei allen Shelly-Kacheln ein direkter Link zum jeweiligen Shelly-Webinterface eingebaut werden?

### Antwort
Ja. Ich habe in jeder Shelly-Kachel einen direkten „Shelly öffnen / Open Shelly“-Link ergänzt.

### Änderungen
- Shelly-Kacheln erweitert um Direktlink pro Gerät:
  - EN: `Open Shelly`
  - DE: `Shelly öffnen`
- Link wird aus der Geräte-IP aufgebaut (`http://<ip>`), falls vorhanden.
- Link erscheint bei allen Shelly-Geräten (inkl. Main).
- Version auf `v0.20` erhöht.

## v0.19

### Frage
Die Kachelbezeichnung für Relais 6-8 soll klar als Bewässerungs-Relais benannt werden, inkl. Übersetzung.

### Antwort
Ich habe die Bezeichnung für die Extra-Kachel entsprechend umbenannt und in EN/DE übersetzt.

### Änderungen
- Umbenennung Kachel `relaysExtra`:
  - EN: `Irrigation relays 6-8`
  - DE: `Bewässerungsrelais 6-8`
- Header-/UI-Version auf `v0.19` erhöht.

## v0.18

### Frage
Für Relais 6/7/8 (8x Board) soll nicht der normale Relay-Toggle verwendet werden, sondern die Pump-Connectoren:
- `/pump/6/triggerPump10s`
- `/pump/7/triggerPump10s`
- `/pump/8/triggerPump10s`

### Antwort
Ich habe die Relais-6-8-Kachel auf dedizierte Pump-Trigger umgestellt und dafür einen eigenen Backend-Action-Endpoint ergänzt.

### Änderungen
- Neuer Backend-Endpoint:
  - `POST /tents/{tent_id}/actions/pump/{pump_idx}/trigger10s`
  - mapped intern auf `/pump/{pump_idx}/triggerPump10s`
  - validiert: nur 8x Boards, nur Pump-Index 6/7/8
- UI-Änderung in Relais-6-8-Kachel:
  - Buttons für 6/7/8 triggern jetzt `triggerPump10s(relayIdx)` statt Relay-Toggle.
  - Layout bleibt identisch zu den anderen Relais-Buttons.
- Version auf `v0.18` erhöht.

## v0.17

### Frage
Bei 8x Boards sollen Relais 6, 7, 8 zusätzlich sichtbar sein – als eigene Kachel, aber im selben Button-Layout wie die ersten 5 Relais.

### Antwort
Ich habe eine separate Relais-6-8-Kachel ergänzt, die nur bei 8x-Boards angezeigt wird und dieselbe Darstellung/Bedienlogik wie die bisherigen Relais nutzt.

### Änderungen
- Neue Dashboard-Kachel: `Relays 6-8` / `Relais 6-8`.
- Sichtbarkeit nur bei `settings.active_relay_count == 8`.
- Buttons für Relais 6/7/8 im gleichen Layout (`relay on/off`) wie Relais 1-5.
- Schaltfunktion identisch über `toggleRelay(relayIdx)`.
- i18n ergänzt (`relaysExtra` EN/DE).
- Version auf `v0.17` erhöht.

## v0.16

### Frage
Es gibt neue Sensorwerte für den Wassertank:
- `sensors.cur.ds18b20Name`
- `sensors.cur.extTempC`

Bitte neben VPD eine neue Kachel plus eigene History hinzufügen.

### Antwort
Ich habe die neue Wassertank-Temperatur vollständig in Dashboard und Verlauf integriert.

### Änderungen
- Neue Live-Kachel neben VPD:
  - Label: Wassertanktemperatur / Tank temperature
  - Wert aus `sensors.cur.extTempC` (inkl. °C/°F Umschaltung)
  - Sensorname aus `sensors.cur.ds18b20Name`
  - eigenes „Update vor …“
- Neue Verlaufskachel inkl. Chart:
  - `Wassertank-Temperaturverlauf`
  - eigener Verlauf aus `/tents/{id}/history`
- Backend-History erweitert:
  - `points[].extTemp` wird aus `sensors.cur.extTempC` mit ausgeliefert.
- i18n ergänzt (DE/EN) für neue Labels.
- Version auf `v0.16` erhöht.

## v0.15

### Frage
Nach den letzten Umbauten (2FA-Kacheln, Entkopplung von Access, QR-Flow, relative Update-Zeit) wurde das Changelog nicht fortgeführt.

### Antwort
Ich habe die Dokumentation jetzt nachgezogen und die neuen 2FA-/UX-Änderungen in einer eigenen Version zusammengefasst.

### Änderungen
- Version auf `v0.15` erhöht (Header + `APP_VERSION`).
- Setup/Auth strukturell getrennt in drei Kacheln:
  - **Access** (nur Benutzername/Passwort/Auth aktiv)
  - **2FA (TOTP)** (separate Aktivierung + eigener Save-Button)
  - **2FA Recovery** (separate Regeneration + eigener Save-Button)
- 2FA-Flow stabilisiert:
  - QR-Code wird lokal über `/auth/qr.png` erzeugt.
  - Enrollment erfolgt mit Verifizierungscode, erst danach wird 2FA final aktiviert.
- UI-Meldungen den Kacheln korrekt zugeordnet:
  - 2FA-Statusmeldungen in 2FA-Kachel
  - Recovery-Meldungen in Recovery-Kachel
  - Access-Meldungen im Access-Bereich
- Console-/JS-Fixes im Setup:
  - behobener JS-Syntaxfehler (verhinderte QR-Rendering)
  - Passwortfeld in Form/Autocomplete eingebettet
- Dashboard-Titelstatus angepasst:
  - statt absolutem Zeitstempel jetzt relative Anzeige wie bei Shelly (z. B. `Update vor 3 Std`).

## v0.14

### Frage
2FA soll bei Aktivierung einen QR-Code anzeigen und Recovery-Codes ausgeben.
Die Loginmaske soll zuerst nur Benutzername+Passwort prüfen und erst im zweiten Schritt den 2FA-Code abfragen.

### Antwort
Ich habe den Auth-Flow auf einen zweistufigen Login umgestellt und die 2FA-Ausgabe in Setup erweitert.
Bei 2FA-Aktivierung werden jetzt QR/URI und Recovery-Codes bereitgestellt.

### Änderungen
- Auth-Login auf 2 Schritte umgestellt:
  1) Benutzername + Passwort
  2) 2FA-Code oder Recovery-Code
- Neue Endpunkte/Logik:
  - `POST /auth/login` liefert bei aktiver 2FA ein Pre-Auth-Token
  - `POST /auth/login/2fa` validiert TOTP/Recovery und erstellt Session
- Setup/Access erweitert:
  - 2FA aktivieren (TOTP)
  - Recovery-Codes neu erzeugen
  - QR-Code Anzeige (über otpauth URI)
  - Recovery-Codes werden direkt nach Erzeugung angezeigt
- Recovery-Codes als Einmal-Codes (hashed + used-Flag) gespeichert.
- Stabilitätsfix: automatische Code-Erzeugung auch wenn `recovery_codes_json` bisher `[]` war.
- Hinweis: Testzustand wurde auf `Auth disabled` zurückgesetzt, damit kein Lockout besteht.

## v0.13

### Frage
Fehlende Pflichtfelder bei der Auth-Konfiguration sollen klar markiert werden.
Außerdem war unklar, dass `admin` nur Platzhalter war und nicht automatisch gesetzt.

### Antwort
Ich habe die Access-Validierung sichtbarer gemacht: fehlende Felder werden rot markiert.
Zusätzlich wird `admin` nun als Standard-Benutzername vorausgefüllt, wenn noch keiner gespeichert ist.

### Änderungen
- Setup/Access: rote Pflichtfeld-Markierung (`input-missing`) für fehlende Auth-Eingaben.
- Bei Backend-Validierungsfehlern (`username`/`password`) wird das passende Feld rot hervorgehoben.
- Standardwert für Benutzername in leerem Zustand auf `admin` gesetzt.
- Version auf `v0.13` erhöht.

## v0.12

### Frage
Kann in der Config ein Passwortgenerator verfügbar gemacht werden?

### Antwort
Ja. Ich habe im Access-Bereich einen Generator-Button ergänzt, der ein starkes Passwort erzeugt und direkt ins Passwortfeld einträgt.

### Änderungen
- Setup/Access: neuer Button **Generate password / Passwort generieren**.
- Generierung direkt im Browser mit `crypto.getRandomValues` (Fallback auf `Math.random`).
- Generierte Länge: 20 Zeichen, gemischtes Zeichenset.
- Version auf `v0.12` erhöht.

## v0.11

### Frage
In der Config soll es Eingaben für Benutzername/Passwort geben sowie einen Schalter, ob Authentifizierung aktiv ist.
Wenn aktiviert, soll die Seite nur noch mit Authentifizierung erreichbar sein.

### Antwort
Ich habe eine konfigurierbare Benutzer-Authentifizierung integriert und in der Setup-Seite als Access-Block verfügbar gemacht.
Bei aktivierter Authentifizierung ist die Anwendung per HTTP Basic Auth geschützt.

### Änderungen
- Backend: Auth-Konfiguration in DB eingeführt (`app_auth_config`).
- Backend: neue Endpunkte
  - `GET /config/auth`
  - `POST /config/auth`
- Backend: HTTP-Basic-Auth Middleware ergänzt (bei aktivierter Auth verpflichtend).
- Setup: neuer Bereich **Access** mit
  - Schalter „Enable user authentication“
  - Benutzername
  - Passwort
  - Speichern-Button
- Passwort wird als SHA-256 Hash gespeichert.
- Header-Version auf `v0.11` aktualisiert.

## v0.10

### Frage
Das Changelog wurde nach mehreren Änderungen nicht weitergeführt. Bitte den Verlauf wieder sauber fortschreiben.

### Antwort
Ich habe das Changelog nachgezogen und die zuletzt umgesetzten Anpassungen gesammelt dokumentiert.
Ab jetzt führe ich jede umgesetzte Änderung wieder direkt in einer neuen Version fort.

### Änderungen
- Rebranding auf **CanopyOps** im Header/App-Titel.
- Navigationsleiste bereinigt:
  - Versionsnummer neben „Navigation“ entfernt.
  - Header-Version auf zweistelliges Format umgestellt (`v0.09`).
- Status-/Update-Anzeigen vereinheitlicht:
  - „Letzte Änderung“ in „Update“ umbenannt.
  - Doppelpunkt nach „Update“ entfernt.
  - Relative Zeitanzeige im Format „vor X Min/Std/Tg“ angepasst.
- Live-Statusdarstellung für Zelte verbessert:
  - Online/Offline am Zeltnamen.
  - Letztes Update neben Status im Titel.
- Shelly-Verbesserungen:
  - „Umschalten“ für alle außer Hauptschalter.
  - Letztes Update je Shelly in der Kartenkopfzeile.
- RTSP-Audio global stumm erzwungen (inkl. video-only Pfad/Fallback).
- Experimente mit Gauges und Sidebar-Bild zurückgebaut bzw. bereinigt (UI wieder stabiler Zustand).

## v0.09

### Frage
Versionsnummern sollen zweistellig geführt werden und im Header sichtbar korrekt aktualisiert werden.

### Antwort
Ich habe das Versionsformat auf zweistellig umgestellt und den Header auf den neuen Stand gebracht.

### Änderungen
- Header-Version in der App-Shell auf `v0.09` gesetzt.
- Künftige Versionen werden im Format `v0.XX` gepflegt.

## v0.8

### Frage
Können die aktuellen Werte als runde Halbkreis-Gauges dargestellt werden, inklusive Sollwerte?

### Antwort
Ja. Ich habe die linearen Mini-Gauges durch SVG-Halbkreis-Gauges ersetzt und Sollwert-Marker ergänzt.

### Änderungen
- Temp/Hum/VPD-Kacheln auf Halbkreis-Gauges umgestellt.
- Temp- und VPD-Sollwerte als Markerpunkt auf dem Halbkreis ergänzt.
- Wertebereiche definiert:
  - Temperatur: 0–40 °C bzw. 32–104 °F
  - Humidity: 0–100 %
  - VPD: 0–3 kPa
- Gauge-Rendering läuft live mit den aktuellen Messwerten.

## v0.7

### Frage
In der History werden bei offline Zelten die Diagramme abgeschnitten.
Wenn keine Werte vorhanden sind, sollen die Diagramme für den gewählten Zeitraum mit Nullwerten gefüllt werden.

### Antwort
Ich habe die History-Logik so angepasst, dass bei leeren Datenpunkten eine synthetische Zeitreihe über den gesamten gewählten Zeitraum erzeugt wird.
Damit bleiben die Diagramme stabil sichtbar und zeigen eine Null-Linie statt eines abgeschnittenen Verlaufs.

### Änderungen
- `loadHistory()` erweitert:
  - Bei `points.length === 0` wird eine Zeitachse über den gesamten Bereich erzeugt.
  - Je nach Zeitraum wird ein sinnvoller Schritt verwendet (5/15/60/360 Minuten).
- Temperatur-, Feuchte- und VPD-Werte werden in diesem Fall als `0` gesetzt.
- Auch nicht-numerische Einzelwerte werden defensiv auf `0` normalisiert.

## v0.6

### Frage
Nicht alle RTSP-Streams sind stumm. Der zweite Stream hat weiterhin Ton.
Alle Zelte sollen grundsätzlich ohne Ton gestreamt werden.

### Antwort
Ich habe die Audio-Unterdrückung für alle Zelte verschärft – sowohl serverseitig als auch clientseitig.
Zusätzlich wird die Stream-Quelle jetzt explizit als `video-only` angefordert.

### Änderungen
- Backend `player_url` erweitert:
  - `muted=1`, `volume=0`, `audio=0`, `media=video`, `defaultMute=1`
- RTSP-Quelle pro Zelt wird für den Player als `#media=video` gesetzt.
- Frontend-Fallback verstärkt:
  - `ensureMutedPlayerUrl(...)` erzwingt dieselben Mute-Parameter erneut.
  - `src` wird clientseitig ebenfalls auf `#media=video` ergänzt, falls fehlend.
- Verifiziert für mehrere Zelte (`/tents/1/latest`, `/tents/19/latest`) mit video-only Player-URL.

## v0.5

### Frage
Bitte Klammern bei der Statusanzeige entfernen. `online` soll grün und `offline` rot dargestellt werden.
Zusätzlich soll neben der Quelle sowohl `Letzter erfolgreicher GET` als auch `Letztes Update` angezeigt werden.
Bitte Übersetzungen berücksichtigen.

### Antwort
Ich habe die Klammern entfernt und die Statuswerte farblich gestaltet.
Die Anzeige enthält jetzt beide Zeitstempel-Texte (lokal formatiert) und ist für DE/EN übersetzt.

### Änderungen
- Statusdarstellung ohne Klammern (`Zeltname online/offline`).
- Farbige Stati eingeführt:
  - online = grün
  - offline = rot
- Header und Tent-Navigation verwenden nun farbige Status-Spans.
- Quellenzeile ergänzt um:
  - `Letzter erfolgreicher GET`
  - `Letztes Update`
- I18N ergänzt: `lastUpdate` (DE/EN) und Statuslabels angepasst.

## v0.4

### Frage
Wenn ein Zelt beim Abruf von `/api/state` nicht erreichbar ist, soll der Status direkt neben dem Zeltnamen als Offline angezeigt werden.
Wenn erreichbar, als Online. Zusätzlich soll sichtbar sein, wann der letzte erfolgreiche GET war.

### Antwort
Ich habe den Online-/Offline-Status an den Zeltnamen gekoppelt und zusätzlich den Zeitpunkt des letzten erfolgreichen Abrufs eingeblendet.
Die Anzeige aktualisiert sich automatisch mit den bestehenden Refresh-Zyklen.

### Änderungen
- Dashboard: Statuslogik für Zelte ergänzt (Online/Offline auf Basis von `captured_at`).
- Dashboard: Zeltnamen in der Navigation zeigen jetzt den Status in Klammern.
- Dashboard: Titelzeile zeigt aktives Zelt als `Name (Online|Offline)`.
- Dashboard: Quellenzeile zeigt zusätzlich `Letzter erfolgreicher GET` mit lokal formatierter Zeit.
- I18N erweitert (DE/EN): `online`, `offline`, `lastSuccess`.
- Statusschwelle gesetzt: älter als 2 Minuten ohne erfolgreichen Poll => Offline.

## v0.3

### Frage
Die Changelog-Seite soll auf Deutsch sein. Nur der Download-Inhalt soll Englisch bleiben.
Außerdem sollen in der Changelog-Seite die Bereiche Frage, Antwort und Änderungen farblich unterschiedlich dargestellt werden.

### Antwort
Ich habe die Changelog-Seite vollständig auf Deutsch umgestellt, inklusive deutscher Download-Beschriftung.
Die Inhalte aus `CHANGELOG.md` werden jetzt als strukturierter Text gerendert und die Abschnitte Frage/Antwort/Änderungen farblich hervorgehoben.
Der Download bleibt unverändert als ZIP mit englischer Installationsanleitung.

### Änderungen
- Changelog-Route überarbeitet: strukturierter Renderer statt reinem `pre`-Block.
- Farbliche Markierung der Abschnittsüberschriften:
  - Frage (gelb)
  - Antwort (cyan)
  - Änderungen (grün)
- Download-Button auf der Changelog-Seite auf Deutsch gesetzt.
- Sichtbare Sidebar-Version auf `v0.3` erhöht.

## v0.2

### Frage
Es soll eine permanente Systembeschreibung geben und darunter Versionseinträge.
Zusätzlich soll ein Projekt-Download mit englischer Installationsanleitung verfügbar sein.

### Antwort
Ich habe eine strukturierte Changelog-Basis eingeführt und einen ZIP-Download für das Projekt ergänzt.

### Änderungen
- Changelog-Link in Dashboard/Setup ergänzt.
- Route `/changelog` erstellt.
- Route `/download/project.zip` erstellt.
- `INSTALL_BACKEND_EN.md` als englische Installationsanleitung angelegt.

## v0.1

### Frage
Initiale Basis für Multi-Tent-Backend mit UI, Historie und Stream.

### Antwort
Erste stabile Basis mit FastAPI, Postgres, go2rtc und zentraler Setup-/Dashboard-Oberfläche.

### Änderungen
- Docker-Stack für API/DB/Stream.
- Tent-Verwaltung und Historie.
- Dashboard mit Kennzahlen, Relais/Shelly, Streams und Charts.
- Setup für Sprache, Theme, Einheiten und Zeitraum.
