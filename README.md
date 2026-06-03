# GrowTent Backend (CanopyOps)

GrowTent Backend ist eine Docker-basierte Backend- und Weboberfläche zur Überwachung und Bedienung von einem oder mehreren GrowTent-Controllern. Die Anwendung sammelt Zustandsdaten der Controller, speichert Historie in PostgreSQL, zeigt Dashboard-Kacheln und Diagramme an und stellt Bedienfunktionen für Shelly-Geräte, Relais, Bewässerung und Kameravorschau bereit.

Das Projekt ist für Controller-Firmware/API vorgesehen, die mit dem `syschelle/GrowTent`-Controller-Projekt kompatibel ist. Ohne kompatiblen Controller funktionieren Basisfunktionen wie Docker, Login und Setup weiterhin, aber Dashboard-Werte, Relaisaktionen, Shelly-Daten und Bewässerungsfunktionen hängen von den tatsächlich gelieferten Controller-Endpunkten und Payload-Feldern ab.

<img width="1851" height="1038" alt="GrowTent dashboard screenshot" src="https://github.com/user-attachments/assets/8fc28274-daa2-48d6-93c0-1ed54d989c6e" />

---

## Überblick

Die Anwendung besteht aus drei Diensten:

| Dienst | Container | Zweck | Von außen erreichbar? |
|---|---|---|---|
| API/UI | `gt_api` | FastAPI-App, Weboberfläche, API, Auth, Proxyfunktionen | ja, standardmäßig `8088` |
| PostgreSQL | `gt_db` | Persistente Speicherung von Konfiguration und Messhistorie | nein |
| go2rtc | `gt_go2rtc` | Interner Helfer für Kamerabilder/RTSP-Streams | nein |

Der normale Zugriff erfolgt über:

```text
http://<server-ip>:8088
```

Wichtige Seiten:

```text
http://<server-ip>:8088/app?page=dashboard
http://<server-ip>:8088/setup
http://<server-ip>:8088/changelog
http://<server-ip>:8088/health
```

---

## Was das Backend macht

GrowTent Backend ist die zentrale Oberfläche für Betrieb, Übersicht und Diagnose Deiner GrowTent-Installation.

Es bietet insbesondere:

- Dashboard für mehrere Zelte bzw. Controller
- Live-Anzeige von Temperatur, Luftfeuchte, VPD, Tanktemperatur, Tankfüllstand und Gerätezuständen
- Speicherung historischer Messwerte in PostgreSQL
- Diagramme für Temperatur, Luftfeuchte, VPD, Alpha-Werte, Energieverbrauch und Speicher-/Systemwerte
- CSV-Export der Historie über die API
- Setup-Oberfläche für Zelte, Authentifizierung, Gäste, Design, Sprache und Einheiten
- Admin- und Gastmodus
- optionale Zwei-Faktor-Authentifizierung für Adminzugriff
- Shelly-Direktabfrage für frischere Leistungs- und Schaltzustände
- Relais- und Bewässerungsaktionen für kompatible Controller
- Kameravorschau über internen go2rtc-Zugriff
- Docker-Helfer zum Zurücksetzen von Admin-Zugangsdaten

---

## Wichtig: Wasserpumpen für Bewässerung

Für die Bewässerungsfunktionen sind **normale Wasserpumpen** vorgesehen, die über geeignete Relais, Netzteile und Schutzmaßnahmen geschaltet werden.

Die Bewässerungslogik im Dashboard und Backend geht praktisch von normalen Wasserpumpen aus, die zuverlässig Wasser fördern, wenn das jeweilige Relais eingeschaltet wird. Plane die Hardware entsprechend:

- Relaisausgänge für Pumpen nur mit passender Spannung und Strombelastbarkeit verwenden
- Pumpen gegen Trockenlauf absichern
- Rückfluss und Siphon-Effekte mechanisch verhindern
- geeignete Sicherungen, Netzteile und Leitungsquerschnitte verwenden
- Wasser und Netzspannung strikt sicher trennen
- manuelle 10-Sekunden-Tests erst durchführen, wenn Schlauchführung und Tank sicher vorbereitet sind

Die App bezeichnet die relevanten Kanäle als Pumpen-/Bewässerungsrelais. Gemeint sind dabei normale Wasserpumpen an den dafür vorgesehenen Relaisausgängen.

---

## Sicherheits- und Netzwerkmodell

Standardmäßig soll nur die API/Weboberfläche nach außen veröffentlicht sein.

| Dienst | Interne Adresse | Host-Port | Hinweis |
|---|---:|---:|---|
| API/UI | `api:8080` | `8088:8080` | einziger veröffentlichter Port |
| PostgreSQL | `db:5432` | keiner | nur im Docker-Netzwerk |
| go2rtc | `go2rtc:1984`, `go2rtc:8554` | keiner | nur im Docker-Netzwerk |

Das bedeutet:

- Browser und Apps greifen auf `http://<server-ip>:8088` zu.
- Die API spricht PostgreSQL intern über `db:5432` an.
- Die API spricht go2rtc intern über `http://go2rtc:1984` an.
- PostgreSQL, go2rtc Web/API-Port `1984` und RTSP-Port `8554` sollen nicht direkt auf dem Host lauschen.

Nach dem Start kannst Du die veröffentlichten Ports prüfen:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Erwartet ist:

```text
8080/tcp -> 0.0.0.0:8088
8080/tcp -> [::]:8088
```

Für `gt_go2rtc` und `gt_db` sollte `docker port` keine Ausgabe liefern. In `ss` sollte für diesen Stack nur `8088` auftauchen.

Wenn `1984` oder `8554` noch sichtbar sind, läuft sehr wahrscheinlich noch ein alter Container oder die aktive Compose-Datei enthält noch alte `ports:`-Einträge. Siehe dazu den Abschnitt [go2rtc-Ports sind noch sichtbar](#go2rtc-ports-sind-noch-sichtbar).

---

## Deployment-Arten

Es gibt zwei Compose-Dateien mit unterschiedlichem Zweck.

### `docker-compose.images.yml`

Diese Datei ist für den normalen Betrieb empfohlen. Die API wird nicht auf dem Zielsystem gebaut, sondern als fertiges Container-Image gezogen.

Vorteile:

- schneller Start auf Raspberry Pi und x86-Servern
- kein lokaler Python-/Build-Aufwand
- gleiche Compose-Datei für ARM64 und AMD64
- deterministischer Betrieb, wenn ein fester Image-Tag verwendet wird

Standard-Image:

```text
ghcr.io/syschelle/growtent-backend-api:latest
```

Optional kann ein fester Image-Tag gesetzt werden:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.248 docker compose -f docker-compose.images.yml up -d
```

### `docker-compose.yml`

Diese Datei ist für lokale Entwicklung und Tests gedacht. Die API wird aus dem lokalen Ordner `./api` gebaut.

Start:

```bash
docker compose up -d --build
```

Für produktive Installationen ist `docker-compose.images.yml` meistens sinnvoller.

---

## Betrieb mit fertigen Images

Projektordner vorbereiten, z. B.:

```bash
cd /opt/growtent-backend
```

Container-Images ziehen:

```bash
docker compose -f docker-compose.images.yml pull
```

Stack starten:

```bash
docker compose -f docker-compose.images.yml up -d --remove-orphans
```

Status prüfen:

```bash
docker compose -f docker-compose.images.yml ps
curl -i http://127.0.0.1:8088/health
```

Erwartet:

```text
HTTP/1.1 200 OK
```

Dashboard öffnen:

```text
http://<server-ip>:8088/app?page=dashboard
```

Setup öffnen:

```text
http://<server-ip>:8088/setup
```

---

## Betrieb mit festem Image-Tag

Für stabile Installationen ist ein fester Image-Tag besser als `latest`, weil genau nachvollziehbar ist, welche Version läuft.

Beispiel:

```bash
cd /opt/growtent-backend

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.248 \
  docker compose -f docker-compose.images.yml pull

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.248 \
  docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Warum `--force-recreate` wichtig sein kann:

Docker ändert Port-Mappings bestehender Container nicht nachträglich. Wenn ein alter `gt_go2rtc`-Container früher `1984` und `8554` veröffentlicht hat, verschwinden diese Ports erst, wenn der Container neu erstellt wurde.

---

## Bestehende Installation aktualisieren

Mit `latest`:

```bash
cd /opt/growtent-backend

docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Mit festem Image-Tag:

```bash
cd /opt/growtent-backend

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.248 \
  docker compose -f docker-compose.images.yml pull

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.248 \
  docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Danach prüfen:

```bash
docker compose -f docker-compose.images.yml ps
docker logs --tail=80 gt_api
curl -i http://127.0.0.1:8088/health
```

---

## GHCR-Zugriff beim Pull

Wenn das Container-Package öffentlich ist, kann Docker das Image ohne Login ziehen.

Wenn das Package privat ist, muss der Server vorher bei GHCR angemeldet werden. Dafür wird ein Token mit Leserechten für Packages benötigt:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

Danach erneut ziehen:

```bash
docker compose -f docker-compose.images.yml pull
```

Typische Fehler:

| Fehler | Bedeutung | Lösung |
|---|---|---|
| `denied` | kein Zugriff auf das Package | Package-Zugriff prüfen oder Docker-Login durchführen |
| `unauthorized` | Login oder Token ungültig | neu einloggen, Token prüfen |
| `manifest unknown` | der angegebene Image-Tag existiert nicht | vorhandenen Tag verwenden oder auf `latest` wechseln, falls verfügbar |

---

## Erstes Setup in der Weboberfläche

1. Stack starten.
2. Im Browser öffnen:

```text
http://<server-ip>:8088/setup
```

3. Mindestens ein Zelt anlegen.
4. Controller-URL eintragen, z. B.:

```text
http://192.168.178.32
```

5. Optional RTSP-URL für Kamera eintragen.
6. Optional Shelly-Zugangsdaten für Shelly-Geräte eintragen.
7. Admin-Authentifizierung aktivieren und Admin-Zugangsdaten setzen.
8. Optional 2FA aktivieren.
9. Dashboard öffnen:

```text
http://<server-ip>:8088/app?page=dashboard
```

Hinweise zur Admin-Konfiguration:

- Der Admin-Benutzername wird in der Setup-UI getrimmt.
- Eine Passwortänderung erfolgt nur, wenn ein neues Passwort eingetragen wird.
- Das neue Passwort muss bestätigt werden.
- Leere Passwortfelder behalten das bestehende Passwort bei.
- Für Passwortfelder wird `autocomplete="new-password"` verwendet, damit Browser/Passwortmanager nicht versehentlich ein altes Passwort einsetzen.

---

## Controller-Kompatibilität

Das Backend erwartet pro Zelt einen HTTP-Controller, der Statusdaten liefert und bestimmte Aktionen unterstützt.

Wichtiger Status-Endpunkt des Controllers:

```text
GET /api/state
```

Typische Aktions-Endpunkte des Controllers, abhängig von Firmware und Hardwareausbau:

```text
POST /relay/{relay_idx}/toggle
POST /startWatering
POST /pump/{pump_idx}/triggerPump10s
POST /pingTank
```

Das Backend ruft diese Controller-Endpunkte über Proxy-Endpunkte auf. Dadurch laufen Bedienaktionen aus der Weboberfläche über die API.

Beispiele im Backend:

```text
POST /tents/{tent_id}/actions/relay/{relay_idx}/toggle
POST /tents/{tent_id}/actions/startWatering
POST /tents/{tent_id}/actions/pump/{pump_idx}/trigger10s
POST /tents/{tent_id}/actions/pingTank
```

Die wichtigsten Controller-Daten werden als JSON-Payload in PostgreSQL gespeichert. Das Dashboard liest daraus Live-Werte und Historie.

---

## Erwartete Mess- und Statuswerte

Die Anwendung ist robust gegenüber fehlenden Einzelwerten, aber aussagekräftige Dashboard- und Verlaufsgrafiken benötigen passende Controller-Felder.

Typische Sensorfelder:

```text
sensors.cur.temperatureC
sensors.cur.humidityPct
sensors.cur.vpdKpa
sensors.cur.temperatureRawC
sensors.cur.humidityRawPct
sensors.cur.vpdRawKpa
sensors.raw.temperatureC
sensors.raw.humidityPct
sensors.raw.vpdKpa
sensors.smoothed.temperatureC
sensors.smoothed.humidityPct
sensors.smoothed.vpdKpa
sensors.cur.extTempC
sensors.cur.ds18b20Name
```

Typische Ziel-/Regelwerte:

```text
settings.grow.targetTemperature
settings.grow.targetVPD
settings.grow.offsetLeafTemperature
settings.grow.minVPDMonitoring
settings.grow.minVPD
settings.active_relay_count
```

Typische Bewässerungswerte:

```text
irrigation.runsLeft
```

Typische Shelly-Felder im Controller-Payload:

```text
settings.shelly.main.ip
settings.shelly.main.gen
settings.shelly.light.ip
settings.shelly.light.line
settings.shelly.humidifier.ip
settings.shelly.heater.ip
settings.shelly.fan.ip
settings.shelly.exhaust.ip
cur.shelly.main.isOn
cur.shelly.main.Watt
cur.shelly.main.Wh
cur.shelly.light.isOn
cur.shelly.light.Watt
```

Das Backend ergänzt und glättet einige Werte, wenn der Controller kurzzeitig `null` liefert oder einzelne Roh-/Glättungswerte fehlen. Für VPD werden bevorzugt Controller-Werte verwendet, damit Live-Kachel und Verlauf möglichst konsistent bleiben.

---

## Bewässerung und Wasserpumpen

Die Bewässerungsfunktionen sind für kompatible 8-Relais-Setups gedacht.

Wichtige Punkte:

- Die automatische Bewässerungsplanung wird nur für Controller mit `settings.active_relay_count == 8` berücksichtigt.
- Die App prüft `irrigation.runsLeft`, um laufende Bewässerung nicht doppelt zu starten.
- Ein Bewässerungsplan kann alle `n` Tage laufen.
- Der Startzeitpunkt kann relativ zu „Licht an“ geplant werden.
- Das Backend bevorzugt echte Licht-an-Ereignisse aus der Historie und nutzt den konfigurierten Shelly-Lichtzeitplan als Fallback.
- Wenn eine Bewässerung startet, wird `irrigation_last_run_date` aktualisiert.
- Manuelle 10-Sekunden-Pumpentests sind für die Pumpenkanäle 6, 7 und 8 vorgesehen.

Backend-Endpunkte:

```text
GET /tents/{tent_id}/irrigation-plan
PUT /tents/{tent_id}/irrigation-plan
POST /tents/{tent_id}/actions/startWatering
POST /tents/{tent_id}/actions/pump/{pump_idx}/trigger10s
```

Hardware-Hinweise:

- Verwende normale Wasserpumpen passend zu Tank, Schlauchlänge, Förderhöhe und Medium.
- Relais müssen zur elektrischen Last der Pumpen passen.
- Induktive Lasten können Relaiskontakte belasten; geeignete Schutzmaßnahmen einplanen.
- Bei Netzspannung sind nur fachgerechte, sichere Installationen zulässig.
- Der 10-Sekunden-Test ist zum Prüfen von Zuordnung, Durchfluss und Schlauchführung gedacht.

---

## Shelly-Integration

Das Backend nutzt Shelly-Daten auf zwei Wegen:

1. Werte, die der GrowTent-Controller bereits in seinem `/api/state`-Payload liefert.
2. Direkte Shelly-Abfragen durch das Backend, um frische Zustände und Leistungswerte zu erhalten.

Unterstützte Gerätearten im Dashboard:

```text
main
light
humidifier
heater
fan
exhaust
```

Direkte Backend-Endpunkte:

```text
GET /tents/{tent_id}/shelly/main/direct
GET /tents/{tent_id}/shelly/exhaust/direct
GET /tents/{tent_id}/shelly/direct-all
GET /tents/{tent_id}/shelly/last-switches
POST /tents/{tent_id}/actions/shelly/{device}/toggle
POST /tents/{tent_id}/actions/shelly/reset-energy
```

Unterstützt werden typische Shelly-Gen1- und Gen2-Antworten:

- Gen1: `/status`, `/relay/0`
- Gen2: `/rpc/Shelly.GetStatus`, `/rpc/Switch.Set`

Shelly-Benutzername und Passwort können pro Zelt gespeichert werden. Das Backend probiert passende Auth-Varianten und fällt bei Bedarf auf unauthentifizierte Abfragen zurück, wenn das Gerät so konfiguriert ist.

---

## Kamera und go2rtc

Kameras werden über eine RTSP-URL pro Zelt konfiguriert. go2rtc läuft intern im Docker-Netzwerk und wird von der API angesprochen.

Interne go2rtc-Adresse:

```text
http://go2rtc:1984
```

Backend-Vorschau:

```text
GET /tents/{tent_id}/preview
```

Die Vorschau liefert ein JPEG-Frame über die API. Dadurch muss der Browser für die normale Dashboard-Vorschau nicht direkt auf go2rtc zugreifen.

Wichtig: Wenn Du einen vollständigen go2rtc-Player oder direkte WebRTC-/RTSP-Funktionen im Browser nutzen möchtest, bräuchte der Browser Zugriff auf go2rtc. Das ist aus Sicherheitsgründen im Standardbetrieb nicht vorgesehen. Standardmäßig bleibt go2rtc intern, und die sichere Vorschau läuft über die API.

---

## Authentifizierung, Admin und Gäste

Die Anwendung unterstützt:

- globalen Auth-Schalter
- Admin-Benutzer
- Admin-Passwort
- optionale Zwei-Faktor-Authentifizierung
- Recovery-Codes
- Gastbenutzer mit Ablaufdatum
- Gastmodus als Read-only-Zugang

Wichtige Regeln:

- Gäste dürfen keine Schreibaktionen ausführen.
- Gäste dürfen nicht auf Konfigurationsseiten zugreifen.
- Wenn Auth deaktiviert ist, werden anonyme Schreibaktionen trotzdem blockiert.
- Setup- und Konfigurationsänderungen sind Admin-Funktionen.

Wichtige Endpunkte:

```text
GET /auth/login
POST /auth/login
POST /auth/login/2fa
POST /auth/logout
GET /auth/whoami
GET /config/auth
POST /config/auth
POST /config/auth/2fa
POST /config/auth/2fa/verify
GET /config/guests
POST /config/guests
PUT /config/guests/{guest_id}
DELETE /config/guests/{guest_id}
```

---

## Admin-Zugang per Docker zurücksetzen

Wenn Du Dich ausgesperrt hast, kannst Du die Admin-Zugangsdaten direkt im API-Container prüfen oder neu setzen.

Status anzeigen:

```bash
docker compose -f docker-compose.images.yml exec api python manage_auth.py status
```

Passwort für den aktuell gespeicherten Admin-Benutzernamen zurücksetzen und 2FA deaktivieren:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker compose -f docker-compose.images.yml exec -T api \
  python manage_auth.py set-admin --password-stdin --disable-2fa
```

Benutzername und Passwort gemeinsam setzen:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker compose -f docker-compose.images.yml exec -T api \
  python manage_auth.py set-admin --username 'MeinAdminName' --password-stdin --disable-2fa
```

Mit festem Container-Namen:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker exec -i gt_api \
  python /app/manage_auth.py set-admin --username 'MeinAdminName' --password-stdin --disable-2fa
```

Interaktive Passwortabfrage mit Bestätigung:

```bash
docker compose -f docker-compose.images.yml exec api \
  python manage_auth.py set-admin --prompt-password --disable-2fa
```

---

## Konfigurations-Backup und Import

Die Anwendung kann Konfigurationsdaten exportieren und wieder importieren.

Backend-Endpunkte:

```text
GET /config/backup/export
POST /config/backup/import
```

Im Export enthalten sind u. a.:

- Schema-Version
- App-Version
- Zelte
- Controller-URLs
- RTSP-URLs
- Shelly-Zugangsdaten
- Bewässerungsplan
- letzter Bewässerungslauf
- Auth-Konfiguration
- Gastbenutzer
- UI-Präferenzen

Der Export ist für Konfigurationssicherung gedacht. Die Messhistorie aus `tent_state` ist nicht dasselbe wie die Setup-Konfiguration und sollte bei Bedarf über PostgreSQL-Backups gesichert werden.

---

## Datenpersistenz

Die Compose-Dateien verwenden ein Docker-Volume für PostgreSQL:

```yaml
volumes:
  db_data:
```

Das Datenbankverzeichnis liegt damit in Docker-verwaltetem Volume-Speicher. Entferne dieses Volume nur, wenn Du die Datenbank bewusst zurücksetzen möchtest.

Volumes anzeigen:

```bash
docker volume ls | grep growtent
```

Datenbank-Backup:

```bash
docker exec gt_db pg_dump -U growtent -d growtent > growtent-backup.sql
```

Datenbank-Restore in eine vorhandene Datenbank:

```bash
cat growtent-backup.sql | docker exec -i gt_db psql -U growtent -d growtent
```

Stack stoppen, ohne Datenbank-Volume zu löschen:

```bash
docker compose -f docker-compose.images.yml down
```

Stack inklusive Datenbank-Volume löschen:

```bash
docker compose -f docker-compose.images.yml down -v
```

Achtung: `down -v` entfernt Docker-Volumes des Stacks und löscht damit die PostgreSQL-Datenbank.

Hinweis für ältere Installationen: Wenn Deine Installation noch ein Bind-Mount wie `./data/postgres:/var/lib/postgresql/data` verwendet, liegen die Daten nicht im Docker-Volume, sondern direkt im Projektordner unter `./data/postgres`. In diesem Fall wirken die PostgreSQL-Initialisierungsvariablen ebenfalls nur beim ersten Anlegen dieses Verzeichnisses.

---

## Wichtige Umgebungsvariablen

| Variable | Beispiel | Bedeutung |
|---|---|---|
| `DATABASE_URL` | `postgresql://growtent:growtent@db:5432/growtent` | PostgreSQL-Verbindung der API |
| `POLL_INTERVAL_SECONDS` | `10` | Intervall für Controller-Polling in Sekunden |
| `RETENTION_DAYS` | `7` | Aufbewahrung der Historie in Tagen |
| `GO2RTC_BASE_URL` | `http://go2rtc:1984` | interne go2rtc-Basisadresse |
| `PROJECT_ROOT` | `/project` | gemounteter Projektpfad im API-Container |
| `GT_API_IMAGE` | `ghcr.io/syschelle/growtent-backend-api:latest` | optionaler Image-Override für `docker-compose.images.yml` |
| `SENSOR_TEMP_MIN_C` | optional | untere Plausibilitätsgrenze für Temperatur |
| `SENSOR_TEMP_MAX_C` | optional | obere Plausibilitätsgrenze für Temperatur |
| `SENSOR_VPD_MIN_KPA` | optional | untere Plausibilitätsgrenze für VPD |
| `SENSOR_VPD_MAX_KPA` | optional | obere Plausibilitätsgrenze für VPD |

---

## API-Übersicht

Auszug wichtiger API-Endpunkte:

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/health` | Healthcheck |
| `GET` | `/setup` | Setup-Oberfläche |
| `GET` | `/app` | App-Shell/Dashboard |
| `GET` | `/dashboard` | Dashboard-Seite |
| `GET` | `/changelog` | Changelog-Seite |
| `GET` | `/grow-guide` | Grow-Guide-Seite |
| `GET` | `/tents` | Zelte auflisten |
| `POST` | `/tents` | Zelt anlegen |
| `PUT` | `/tents/{tent_id}` | Zelt ändern |
| `GET` | `/tents/{tent_id}/latest` | letzter gespeicherter Zustand |
| `GET` | `/tents/{tent_id}/history` | historische Messwerte |
| `GET` | `/tents/{tent_id}/preview` | Kamera-Frame über API |
| `GET` | `/api/poll-errors` | Polling-Fehler als JSON |
| `GET` | `/poll-errors` | Polling-Fehlerseite |
| `GET` | `/config/backup/export` | Konfiguration exportieren |
| `POST` | `/config/backup/import` | Konfiguration importieren |
| `GET` | `/download/project.zip` | Projektpaket herunterladen |

Schreibende Endpunkte sind durch Auth-/Gastregeln geschützt. Gastbenutzer sind read-only.

---

## Betriebsprüfung nach Änderungen

Nach Compose- oder Image-Änderungen:

```bash
cd /opt/growtent-backend

docker compose -f docker-compose.images.yml ps
docker logs --tail=80 gt_api
docker logs --tail=80 gt_db
docker logs --tail=80 gt_go2rtc
curl -i http://127.0.0.1:8088/health
```

Ports prüfen:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Erwartung:

- `gt_api` veröffentlicht `8088 -> 8080`
- `gt_go2rtc` veröffentlicht keinen Host-Port
- `gt_db` veröffentlicht keinen Host-Port
- auf dem Host lauscht für diesen Stack nur `8088`

---

## Troubleshooting

### API startet nicht: Datenbank-Login schlägt fehl

Symptome in `docker logs gt_api`:

```text
psycopg2.OperationalError: password authentication failed for user "growtent"
```

Oder in `docker logs gt_db`:

```text
FATAL: role "growtent" does not exist
```

Häufige Ursache: Die PostgreSQL-Datenbank wurde bereits früher mit anderen Zugangsdaten initialisiert. `POSTGRES_USER`, `POSTGRES_PASSWORD` und `POSTGRES_DB` werden nur verwendet, wenn PostgreSQL ein leeres Datenverzeichnis initialisiert.

Bei frischer Installation ohne wichtige Daten:

```bash
docker compose -f docker-compose.images.yml down -v
docker compose -f docker-compose.images.yml up -d
```

Bei bestehender Installation mit wichtigen Daten zuerst Rollen prüfen:

```bash
docker exec -it gt_db sh -lc 'psql -d postgres -c "\\du"'
```

Wenn ein bekannter Superuser existiert, kann damit die Rolle `growtent` angelegt oder repariert werden. Wenn weder `postgres` noch `growtent` existieren, stammt das Datenverzeichnis sehr wahrscheinlich aus einer anderen alten Installation. In diesem Fall vorsichtig vorgehen und zuerst ein Backup des Datenverzeichnisses erstellen.

### Fehler bei Here-Document und `docker exec`

Wenn Du SQL per Here-Document in einen Container pipe-st, verwende `-i`, nicht `-it`:

```bash
docker exec -i gt_db psql -U postgres -d postgres <<'SQL'
SELECT 1;
SQL
```

`-t` verlangt ein Terminal und passt nicht zu `<<'SQL'`.

### API-Port `8088` ist nicht sichtbar

Effektive Compose-Konfiguration prüfen:

```bash
docker compose -f docker-compose.images.yml config | grep -A30 "api:"
```

Erwartet:

```yaml
ports:
  - mode: ingress
    target: 8080
    published: "8088"
```

API-Container neu erstellen:

```bash
docker compose -f docker-compose.images.yml rm -sf api
docker compose -f docker-compose.images.yml up -d api
```

Prüfen:

```bash
docker port gt_api
curl -i http://127.0.0.1:8088/health
```

### go2rtc-Ports sind noch sichtbar

Symptom:

```bash
docker port gt_go2rtc
```

zeigt z. B.:

```text
1984/tcp -> 0.0.0.0:1984
8554/tcp -> 0.0.0.0:8554
```

Dann wurde `gt_go2rtc` noch mit einer alten Port-Konfiguration erstellt oder die aktive Compose-Datei enthält noch `ports:` für go2rtc.

Effektive Konfiguration prüfen:

```bash
docker compose -f docker-compose.images.yml config | grep -A25 "go2rtc:"
```

Unter `go2rtc:` darf kein `ports:` stehen. Erlaubt ist höchstens `expose:`, weil `expose` nur intern dokumentiert und keinen Host-Port veröffentlicht.

Nach alten Port-Einträgen suchen:

```bash
grep -Rni --include='*.yml' --include='*.yaml' -E '1984|8554|go2rtc|ports:' .
```

Alte Container entfernen und neu erstellen:

```bash
docker compose -f docker-compose.images.yml down --remove-orphans
docker rm -f gt_go2rtc gt_api gt_db 2>/dev/null || true

docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Erneut prüfen:

```bash
docker port gt_go2rtc
ss -tulpn | grep -E ':1984|:8554' || true
```

Erwartet: keine Ausgabe.

### Herausfinden, welche Compose-Datei einen Container erstellt hat

```bash
docker inspect gt_go2rtc --format 'Project={{index .Config.Labels "com.docker.compose.project"}} Files={{index .Config.Labels "com.docker.compose.project.config_files"}} Service={{index .Config.Labels "com.docker.compose.service"}} PortBindings={{json .HostConfig.PortBindings}}'
```

Wenn bei `PortBindings` noch `1984/tcp` oder `8554/tcp` auftauchen, stammt das aus der Container-Konfiguration, mit der der Container erstellt wurde.

### GHCR-Pull schlägt fehl

Bei:

```text
denied
```

fehlt meistens der Zugriff auf das Package oder der Docker-Login.

Bei:

```text
manifest unknown
```

existiert der angegebene Image-Tag nicht.

Prüfen:

```bash
docker pull ghcr.io/syschelle/growtent-backend-api:latest
```

Oder mit festem Tag:

```bash
docker pull ghcr.io/syschelle/growtent-backend-api:v0.248
```

### Dashboard zeigt alte oder leere Werte

Mögliche Ursachen:

- Controller ist nicht erreichbar.
- Controller-URL im Setup ist falsch.
- Controller liefert kein kompatibles `/api/state`.
- Polling schlägt wiederholt fehl.
- Es gibt noch keine gespeicherten Historienpunkte.
- Shelly-Geräte sind aus dem API-Container nicht erreichbar.

Prüfen:

```bash
docker logs --tail=120 gt_api
curl -i http://127.0.0.1:8088/api/poll-errors
```

Zusätzlich im Setup die Controller-URL kontrollieren.

### Kameravorschau funktioniert nicht

Prüfen:

- RTSP-URL im Setup korrekt?
- Kamera aus dem Docker-Netz erreichbar?
- go2rtc-Container läuft?
- API kann intern `http://go2rtc:1984` erreichen?

Logs:

```bash
docker logs --tail=120 gt_go2rtc
docker logs --tail=120 gt_api
```

Test über API:

```bash
curl -I http://127.0.0.1:8088/tents/1/preview
```

---

## Projektstruktur

```text
api/main.py              FastAPI-Bootstrap, Router-Einbindung
api/app.py               Haupt-/Legacy-App mit UI, Polling, Auth, Datenlogik
api/manage_auth.py       Docker-Helfer für Admin-Zugangsdaten
api/routes/              zusätzliche API-Router
api/services/            Service-Helfer
api/db/                  Datenbank-Helfer
api/core/                Konfiguration und Dependencies
api/models/              Schemas
api/static/              statische Assets, z. B. Chart.js Bundle
docker-compose.yml       lokaler Build aus ./api
docker-compose.images.yml Betrieb mit fertigem API-Image
DEPLOY_IMAGES.md         kompakte Deploy-Notizen
CHANGELOG.md             Projekt-Changelog
api/CHANGELOG.md         API-/App-Changelog
```

Hinweis zur Architektur: Die Anwendung wird schrittweise von einer großen Legacy-Datei in modulare FastAPI-Komponenten überführt. Deshalb liegt noch viel Logik in `api/app.py`, während neue oder ausgelagerte Teile bereits unter `routes`, `services`, `db`, `core` und `models` liegen.

---

## Lizenz

Siehe `LICENSE`.
