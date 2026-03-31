# Aufgabe – GrowTent Backend PoC

## Ziel
Ein schlankes, dockerfähiges Backend-System für die ESP32-GrowTent-Anwendung aufbauen, mit schöner Weboberfläche und Unterstützung für mehrere Zelte.

## Aktuelle Anforderungen (von Sylvio)

1. **Mehrere Zelte verwalten**
   - Das Backend muss mehrere Grow-Zelte (Tents) unterstützen.
   - Jedes Zelt soll eindeutig verwaltbar sein (Name, Quelle, Status).

2. **Datenbank-Speicherung**
   - Mess- und Statusdaten sollen persistent in einer Datenbank gespeichert werden.
   - Historie muss abrufbar sein (mindestens letzter Zustand, perspektivisch Zeitverlauf).

3. **Kein InfluxDB / kein Grafana**
   - Diese beiden Komponenten dürfen **nicht** verwendet werden.
   - Stattdessen klassischer Stack mit API + relationaler DB + eigener UI.

4. **MQTT-Server enthalten**
   - Das System soll einen integrierten MQTT-Broker enthalten.
   - Telemetrie und Kommandos sollen über MQTT möglich sein.

5. **Docker-basiert**
   - Gesamtes System soll per Docker / Docker Compose laufen.
   - Einfache Inbetriebnahme über `docker compose up -d --build`.

6. **Schlank, aber mit schöner Oberfläche**
   - Architektur soll ressourcenschonend bleiben.
   - Trotzdem moderne, gut nutzbare Oberfläche für Monitoring/Verwaltung.

7. **Schnittstelle erstes Zelt**
   - Erste Datenquelle ist:
     - `http://192.168.178.32/api/state`
   - Diese Quelle soll regelmäßig gepollt und gespeichert werden.

## Bereits umgesetzter PoC-Stand

- Verzeichnis: `/home/openclaw/.openclaw/workspace/growtent-backend-poc`
- Docker-Services vorhanden:
  - `api` (FastAPI)
  - `db` (PostgreSQL)
  - `go2rtc`
- Polling auf `http://192.168.178.32/api/state` aktiv
- Speicherung in PostgreSQL aktiv
- API-Testendpunkte:
  - `GET /health`
  - `GET /tents`
  - `GET /tents/{id}/latest`

## Nächste Ausbauschritte

1. Web-Frontend hinzufügen (Multi-Tent Dashboard)
2. Tent-Management (CRUD) über API
3. Historienabfrage (Zeitfenster, Aggregation)
4. Benutzer-/Rechtemodell (optional, aber empfohlen)
5. MQTT-Topic-Konzept dokumentieren (Telemetry/Command/Status)
6. Produktionshärtung (Reverse Proxy, TLS, Backups, Monitoring)
