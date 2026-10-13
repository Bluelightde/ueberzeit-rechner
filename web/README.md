# Überzeit – Server-Version

Der Überzeit-Rechner im Browser und als **App auf dem Handy**. Gerechnet wird mit denselben Regeln wie in der
Desktop-App (`../kern.py`): Tagessoll je Wochentag, Feiertage, Sondertage, Pausen nach ArbZG, Höchstarbeitszeit,
Gleitzeitabbau – auf die Minute gleich. Jede Person hat ihre eigenen Daten. Die Desktop-App bleibt unverändert und
braucht die Server-Version nicht.

## Was sie kann

- **Aussehen wie die Desktop-App:** gleiche Reiter, Breeze-Farben (hell/dunkel), Eintragstabelle mit „Bearbeiten“ und
  „Löschen“, Kalender-Heatmap. Am Handy stehen die Reiter unten.
- **Eingabe & Liste:** Gesamtsaldo, Urlaubskonto, **Kommen / Feierabend** mit laufender Uhr und der Uhrzeit, zu der das Tagessoll
  erreicht ist. Eintragen mit **Live-Vorschau**: Pause, Tag-Saldo, Ende fürs Tagessoll, Warnungen bei Überschneidung,
  Ruhezeit unter 11 h und Höchstarbeitszeit.
- **Arten:** Arbeit (mit Uhrzeiten oder als Korrektur in Minuten), Urlaub, Krank, Gleitzeitabbau, Feiertag, Elternzeit –
  über mehrere Tage, Wochenenden und Feiertage werden übersprungen. Eigenes Tagessoll je Eintrag.
- **Eintragstabelle** je Monat (mehrtägige Abwesenheiten als ein Block), **Kalender-Heatmap** mit Tagessaldo, Feiertagen,
  Abwesenheiten und Bereitschaft, **Statistik** (Monatssaldo, Ø je Wochentag, Serien), **Ziel** (Überstunden für eine
  freie Zeit ansparen), **Bereitschaft**, **Einstellungen** wie in der Desktop-App, hell/dunkel.
- **Austausch mit der Desktop-App** (Mehr → Daten aus der Desktop-App): `ueberstunden_daten.db` und
  `ueberstunden_settings.json` hochladen. Export als Datenbank im Desktop-Format (dort unter *Einstellungen →
  Datenbank-Speicherort* wählbar) und als CSV.
- **Als App installierbar** (Web-App-Manifest, Service Worker): eigenes Symbol, startet ohne Browserleiste, zeigt ohne
  Verbindung den zuletzt geladenen Stand.

Nicht in der Server-Version: die Anmeldezeit des Rechners als Startzeit und der Tab „Anwesenheit“ (beides liest das
Betriebssystem des Desktop-Rechners) sowie Excel/PDF-Export.

## Schnellstart (Docker Compose)

```bash
git clone https://github.com/Bluelightde/ueberzeit-rechner.git && cd ueberzeit-rechner
cp web/.env.beispiel web/.env            # SECRET_KEY setzen, Authentik eintragen (siehe unten)
mkdir -p web/daten && sudo chown 1001:1001 web/daten
docker compose up -d --build
docker compose logs app | grep -A3 "ERSTER START"   # Notzugang (nur beim allerersten Start)
```

Danach läuft die App auf Port **5026** (`UZ_PORT` in der Umgebung ändert ihn). Für die Installation als App auf dem Handy
braucht es **HTTPS**, also einen Reverse Proxy (z. B. Nginx Proxy Manager) mit Zertifikat davor: `HINTER_PROXY=1`,
`PROXY_ADRESSEN=<IP des Proxys>`, `APP_URL=https://…`.

## Anmeldung über Authentik

OAuth2/OpenID-Provider (vertraulich, Authorization Code), Redirect-URI `https://<adresse>/anmelden/authentik/zurueck`,
Scopes `openid profile email`. In `web/.env`: `OIDC_ISSUER` (`https://auth…/application/o/<slug>/`), `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, **`OIDC_GRUPPE`**. Nur Mitglieder dieser Gruppe kommen hinein (bei jeder Anmeldung geprüft); wer
drin ist, bekommt beim ersten Mal ein eigenes, leeres Konto. Ohne `OIDC_GRUPPE` ist die Authentik-Anmeldung aus.

Das Passwortformular (Notzugang) gibt es nur direkt im LAN, nicht über den Proxy (`LOKALE_ANMELDUNG=intern`).
Alle Sitzungen einer Person beenden: `docker compose exec app python app.py abmelden <name>`.

## Betrieb

| | |
|---|---|
| Daten | `web/daten/ueberzeit.db` (SQLite, WAL, Dateirechte 600) |
| Sicherung | `docker compose exec -T app python sicherung.py /daten/ueberzeit.db /daten/sicherung 14` – konsistent im laufenden Betrieb (`sqlite3.backup`), prüft `integrity_check`, behält 14 Stände |
| Gesundheit | `GET /version` → `{"version": …, "datenbank": "ok"}` (503 bei Datenbankfehler); Docker-Healthcheck nutzt das |
| Protokoll | journald, Tag `ueberzeit` |
| Update | `git pull && docker compose up -d --build` |

## Entwicklung und Prüfungen

```bash
python -m venv venv && venv/bin/pip install -r web/requirements.txt
SECRET_KEY=dev venv/bin/python web/app.py                      # http://127.0.0.1:5026
SECRET_KEY=x venv/bin/python -m unittest discover -s web/tests  # 20 Prüfungen
```

Symbole neu erzeugen (aus der Geometrie von `create_icon.py`): `python web/werkzeuge/symbol.py`.

## Aufbau

| Datei | Inhalt |
|---|---|
| `app.py` | Flask: Konfiguration, Anmeldung (OIDC + Notzugang), CSRF, Sicherheitsköpfe, alle Seiten |
| `speicher.py` | SQLite-Schema (Einträge wie in der Desktop-Datenbank, mit `benutzer_id`), Einstellungen je Person, Neuberechnung |
| `auswertung.py` | Vorschau, Ende fürs Tagessoll, Urlaub, Ziel, Kalender, Statistik – rechnet nur mit `kern.py` |
| `austausch.py` | Desktop-Datenbank/Einstellungen einlesen (nur lesend geöffnet, geprüft), Export als Desktop-DB und CSV |
| `laender.py` | Länder und Regionen der Feiertage mit deutschen Namen |
| `oidc.py` | OpenID Connect mit PKCE, nur Standardbibliothek |

## Sicherheit

- Content-Security-Policy ohne Inline-Skripte, `X-Frame-Options: DENY`, HSTS über HTTPS, Cookies `HttpOnly`/`SameSite=Lax`
  (`Secure` hinter HTTPS), CSRF-Token für jedes Formular und die Live-Rechnung.
- Jede Abfrage ist an die angemeldete Person gebunden (`benutzer_id`); fremde Einträge ergeben 404.
- Hochgeladene Desktop-Datenbanken werden nur lesend geöffnet, auf SQLite-Kopf und `quick_check` geprüft und danach
  gelöscht; aus Einstellungsdateien werden nur bekannte Schlüssel mit geprüften Werten übernommen.
