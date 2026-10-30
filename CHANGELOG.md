# Changelog

All notable changes to Überzeit Rechner are documented here.

---

## [1.10.0] – 2026-10-20

- **Läuft im Hintergrund weiter** — Schließen versteckt das Fenster nur; die App sitzt als Symbol in der Taskleiste
  (Windows: Infobereich, macOS: Menüleiste, Linux: KDE/XFCE von Haus aus, GNOME mit der Erweiterung „AppIndicator“)
  und meldet Anwesenheit und Einträge weiter an die Server-Version. Menü am Symbol: Öffnen, Jetzt abgleichen, Beenden.
  Ohne Infobereich beendet das Schließen die App wie bisher. Einstellung „Beim Schließen im Hintergrund weiterlaufen“.
- **Mit dem Rechner starten** — Einstellung „Mit dem Rechner starten – ohne Fenster, nur als Symbol“ trägt den
  Autostart ins System ein (Windows: `HKCU\…\Run`, Linux: `~/.config/autostart`, macOS: LaunchAgent) und startet mit
  `--hintergrund` (`hintergrund.py`).
- **Nur eine laufende App** — ein zweiter Start holt das vorhandene Fenster nach vorn (Sperre `.laeuft.lock` neben
  der Datenbank), statt die Datenbank doppelt zu öffnen.
- **Urlaubskonto entfernt** — Anzeige „Urlaub: x/30 Tage übrig“ und Einstellung „Urlaubsanspruch“ sind weg. Die
  Eintragsart „Urlaub“ bleibt.

## Server-Version 1.10.2 – 2026-10-30

- **Statusleiste oben wieder dunkel** — der Seitenwechsel ohne Neuladen übernahm die helle Vorgabefarbe der neuen Seite und überschrieb die Farbe des Dunkelmodus.

## Server-Version 1.10.1 – 2026-10-30

- **Seitenwechsel ruhiger** — die neue Seite erscheint erst, wenn ihre Skripte gelaufen sind; Zurück merkt sich die Stelle, ohne den Verlauf anzufassen.

## Server-Version 1.10.0 – 2026-10-30

- **Kein Ladebalken mehr** — Links und Formulare wechseln die Seite ohne Neuladen (gemeinsames `weich.js` der
  Homelab-Apps); Chrome zeigt oben keinen Balken mehr. Anker nach Umleitungen kommen über `weich_anker` an.
  Abmelden lädt weiter echt.

## Server-Version 1.9.4 – 2026-10-27

- **Menüwechsel schneller** — Symbol-Dateien tragen die Version in der Adresse und werden zwischengespeichert (vorher fragte jede Seite erst beim Server nach); Menüseiten werden beim Antippen vorgeladen (Speculation Rules), wie Bilderrahmen 1.3.1.

## Server-Version 1.9.3 – 2026-10-27

- **Kalender bleibt gleich groß** — immer sechs Wochenzeilen und feste Kästchenhöhe; vorher wuchs und schrumpfte er
  mit 4/5/6 Wochen und mit umbrechenden Salden wie „(-1h 1m)“.
- **Heute-Knopf** im Kalender, springt zum aktuellen Monat.

## Server-Version 1.9.2 – 2026-10-27

- **Kalender am Handy ohne Sprung** — ein angetippter Tag kommt als Blatt von unten, statt die Seite neu zu laden und
  zum Abschnitt unter dem Monat zu springen. Schließen mit ✕, Tippen daneben oder Zurück. Am Rechner bleibt das
  Popover am Tag.
- Browsertests: zwei Tests (Rückfrage-Dialog, Tages-Popover) standen hinter `if __name__ == '__main__'` und liefen nie.

## Server-Version 1.9.1 – 2026-10-21

- Werkzeug 3.1.9 (Sicherheitsupdate, CVE-2026-102598: `safe_join()` unter Windows – der Server läuft unter Linux).

## Server-Version 1.9.0 – 2026-10-21

- **Bereitschaft im Tages-Popup** — eigene Zeile mit Zeitspanne, Uhrzeit (oder „ganztägig“), Notiz und Löschen;
  nach dem Löschen zurück zum Tag. Die Seite „Bereitschaft“ nutzt dieselbe Zeile.
- **Rückfragen als Dialog im Design der Seite** statt des Browserfensters (gemeinsames `frage.js`/`frage.css`,
  wie in Kugelzeit, Zugstatistik, Wohnungssuche und Wichteln). Enter = OK, Esc = Abbrechen.

## Server-Version 1.8.3 – 2026-10-20

- **Bereitschaftslinie ragt nicht mehr über den Rand** — am Monatsende und am Zeilenende (Sonntag/Montag) endet die
  Linie am Kästchen, auch wenn die Bereitschaft weitergeht.

## Server-Version 1.8.2 – 2026-10-20

- **Bereitschaft als durchgehende Linie** — mehrere Tage Bereitschaft verbinden sich über die Lücken zwischen den
  Kästchen; abgerundet nur an Anfang und Ende. Am Rechner liegt die Linie bei etwa zwei Dritteln der Höhe über dem
  Saldo statt am unteren Rand.

## Server-Version 1.8.1 – 2026-10-20

- **Kalendertag aus einer Zeitspanne zeigt die ganze Spanne** — z. B. „05.10. – 16.10.2026 · Elternzeit · 10 Tage“
  wie in der Liste; Bearbeiten öffnet den ganzen Block.

## Server-Version 1.8.0 – 2026-10-20

- **Kalender am Rechner: Tag als Popover am Kästchen** — statt rechts daneben (der Monat schrumpfte) öffnet ein
  angeklickter Tag ein Popover direkt neben dem Tag, mit Pfeil; rechts, sonst links. Schließen mit ✕, Esc, Klick
  daneben oder nochmal auf den Tag. Nach Bearbeiten/Löschen ist es wieder offen. Am Handy unverändert.

## Server-Version 1.7.0 – 2026-10-20

- **Urlaubskonto entfernt** — „Urlaub: x/30 Tage übrig“ auf der Startseite und „Urlaubstage im Jahr“ in den
  Einstellungen. Die Eintragsart „Urlaub“ bleibt.

## Server-Version 1.6.0 – 2026-10-19

- **Kalender am Rechner füllt das Fenster** — Zeilenhöhe aus Fensterhöhe und Wochenzahl; der gewählte Tag steht ab
  1100 px rechts neben dem Monat.

---

## Server-Version 1.5.5 – 2026-10-17

- **Offene Datenbankverbindung beim Start** — die Verbindung aus `speicher.schema_anlegen()` blieb offen, weil
  `teardown_appcontext` in `erstelle_app()` noch nicht eingetragen war; jetzt wird sie dort geschlossen.

---

## [1.9.3] – 2026-10-14

- **Anmeldezeit wird wieder erkannt (Linux)** — die gebaute App gab ihre mitgelieferten Bibliotheken
  (`LD_LIBRARY_PATH` → `_internal`) an `journalctl`, `last` und `who` weiter; `journalctl` brach mit
  „version OPENSSL_3.4.0 not found“ ab, die Startzeit fiel auf den Standard zurück und die Anwesenheit fehlte.
  Systemprogramme laufen jetzt mit der Umgebung des Systems (`umgebung.system_env`), auch beim Neustart nach
  einem Update und unter macOS (`hdiutil`, `ditto`).

## [1.9.1] – 2026-10-14

- **Einstellungsfenster breit genug für alle Reiter** — der Reiter „Server-Version“ war abgeschnitten. Das Fenster
  richtet seine Breite jetzt nach den Reitern (Schrift, Sprache, Stylesheet), mindestens wie bisher 650 px.

## [1.9.0] – 2026-10-14

Desktop 1.9.0, Server-Version 1.4.0 und 1.5.0.

### Added
- **Server-Version 1.5.4: Startseite springt beim Laden nicht mehr** — Felder, die nur bei Abwesenheit, eigenem
  Tagessoll oder Korrektur gebraucht werden, waren beim ersten Zeichnen kurz sichtbar und verschwanden erst durch das
  Skript; die Pause sprang von 0 auf 30 und die Vorschau zeigte „Berechne …“. Der Server liefert Sichtbarkeit, Pause
  und Vorschau jetzt schon fertig (Startseite und Bearbeiten), die Eingabe-Karte behält ihre Höhe.
- **Server-Version 1.5.3: Woche auf der Startseite, Kopfzeile in einer Zeile** — am Rechner steht links unter der
  Stempeluhr die laufende Woche (Mo–So mit Zeiten, Abwesenheit und Tag-Saldo, darunter der Wochensaldo; ein Tag öffnet
  ihn im Kalender), am Handy unter der Eingabe. Seite und Kopf sind am Rechner breiter (1280 px); Marke und Reiter
  brechen nicht mehr um, bei knapper Breite zeigen die Reiter die Kurznamen.
- **Server-Version 1.5.2: Uhr nur am Handy, keine hängenden Rahmen** — am Desktop (Maus/Touchpad als Hauptzeiger)
  bleibt das normale Uhrzeitfeld zum Eintippen, die eigene Uhr gibt es nur bei Touch (`uhr.js`, geteilt). Nach dem
  Antippen von Häkchen, Datum oder Auswahllisten bleibt kein Fokus-Rahmen mehr stehen; Tippfelder zeigen beim Schreiben
  nur einen farbigen Rand.
- **Server-Version 1.5.1: Uhr öffnet mit Animation, kein weißer Kasten beim Antippen** — die Uhr blendet beim Öffnen
  und Schließen ein bzw. aus und wächst dabei leicht (wie die Android-Dialoge, `@starting-style`), der Hintergrund
  blendet mit. Die Antipp-Markierung von Chrome auf Android (grauer/weißer Kasten) ist in der ganzen App abgeschaltet;
  Rückmeldung kommt über `:active`. Gilt über `gemeinsam.py` auch für Notizen, Vorratsliste und Wohnungssuche.
- **Server-Version 1.5.0: eigene Uhr statt Android-Systemuhr und gründlichere Oberfläche** — Uhrzeitfelder öffnen die
  gemeinsame Uhr der Homelab-Apps (`web/static/js/uhr.js`, `css/uhr.css`, gepflegt mit `gemeinsam.py` zusammen mit
  Notizen/Vorratsliste/Wohnungssuche): Zifferblatt wie bei Android, Zahlen tippen, „Ohne“ für optionale Zeiten, passt
  aufs Handy. Das gestreckte Häkchen beim Tagessoll (bis 234 px breit) ist ein normales Häkchen „Eigenes Tagessoll für
  diesen Tag“, das Zeitfeld erscheint erst dann. Klarere Beschriftungen (Beginn/Ende, Pause in Minuten, Korrektur,
  Anlass optional, „Arbeitsbeginn verwerfen“, Hinweis „ohne Uhrzeit = jetzt“ beim Feierabend), Beschriftungen für die
  Tabellenfelder der Einstellungen, größere Schrift in Kalender, Statistik und Leiste, Hinweis zum Abgleich auf der
  Austausch-Seite. Neue Browser-Tests (`web/tests/test_browser.py`, Playwright, `web/requirements-dev.txt`).
- **Abgleich der Einträge mit der Server-Version in beide Richtungen** (Desktop 1.9.0, Server 1.4.0) — mit dem
  Gerätezugang gleicht die Desktop-App alle Einträge und Bereitschaften mit der Server-Version ab: beim Start, alle
  5 Minuten und 20 Sekunden nach jeder Änderung. Was am Desktop oder im Browser (Web-App) eingetragen, geändert oder
  gelöscht wird, steht danach auch auf der anderen Seite; der Gesamtsaldo stimmt überall. Abgeglichen wird je Tag
  (`abgleich.py`, `kern.tag_inhalt`/`tag_hash`); wurde derselbe Tag auf beiden Seiten geändert, gilt die neuere
  Änderung. Nach „Aus Backup wiederherstellen“ gewinnt der wiederhergestellte Stand. Schalter unter Einstellungen →
  Server-Version („Einträge in beide Richtungen abgleichen“). Einstellungen werden nicht übertragen.
  Datenbank: Desktop-Schema 4 (`tag_geaendert`, `abgleich_stand`, Trigger), Server-Schema 3 (`tag_stand`, Trigger);
  Schnittstellen `GET /api/geraet/tage`, `POST /api/geraet/tage/holen`, `POST /api/geraet/tage/schreiben`.
- **Server-Version `web/`** — Überzeit läuft zusätzlich im Browser und als installierbare App (PWA) auf dem Handy, z. B. im
  eigenen Homelab mit Docker Compose (`compose.yml` in der Repo-Wurzel, Anleitung `web/README.md`). Jede Person hat eigene
  Daten; Anmeldung über OpenID Connect (Authentik) mit Gruppenprüfung, Notzugang per Passwort nur direkt im LAN.
  - Heute: Gesamtsaldo, Urlaubskonto, „Kommen/Feierabend“ mit laufender Uhr, Eintragen mit Live-Vorschau (Pause,
    Tag-Saldo, Ende fürs Tagessoll, Überschneidung, Ruhezeit, Höchstarbeitszeit).
  - Einträge (Monatsliste, mehrtägige Abwesenheiten zusammengefasst), Kalender mit Tagessaldo, Feiertagen, Abwesenheiten
    und Bereitschaft, Statistik, Ziel (Überstunden ansparen), Bereitschaft, Einstellungen wie in der Desktop-App.
  - **Austausch mit der Desktop-App:** `ueberstunden_daten.db` und `ueberstunden_settings.json` hochladen; Export als
    Datenbank im Desktop-Format (dort als Datenbank-Speicherort wählbar) und als CSV.
  - **Aussehen wie die Desktop-App** (Server 1.1.0): Breeze-Farben hell/dunkel, Reiter „Eingabe & Liste“, „Ziele &
    Dashboard“, „Kalender-Heatmap“, „Bereitschaft“, „Diagramm & Statistik“; Gesamt-Saldo, Eingabe, Werkzeugleiste
    (Filter, Import, Export, Einstellungen) und Eintragstabelle (Datum | Zeitraum | Überstunden | Anlass | Aktion) wie im
    ersten Reiter; Kalender als Heatmap mit den Desktop-Farben. Am Handy Reiter unten und eine schmalere Tabelle.
  - **Anwesenheit von der Desktop-App** (Server 1.2.0): Die Desktop-App meldet die Login-/Logout-Zeiten
    (`server_sync.py`, Einstellungen → Server-Version, Gerätezugang aus der Server-Version) beim Start und alle
    30 Minuten im Hintergrund. Der Server zeigt sie im Reiter „Anwesenheit“ und im Kalender, schlägt die Anmeldezeit als
    Start vor („Login-Zeit als Startzeit verwenden“) und bietet „Kommen um 07:12“. Austausch/Export nehmen
    `device_login` mit.
- **Server-Version 1.3.0: Look wie das Homelab-Dashboard** (`dash.rm-weiss.de`) statt wie die Desktop-App — gleiche
  Farben hell/dunkel, Systemschrift, weiße Karten mit feinem Rand und runden Ecken, kleine graue Abschnittstitel,
  blauer Akzent, Reiter als Leiste, Arten als Chips, Kalender mit abgerundeten Tagen. Am PC stehen Stempeluhr und
  Eingabe nebeneinander. Aufbau und Inhalte unverändert.
- **Updates aus der App** — die Desktop-App sucht beim Start und alle 6 Stunden auf GitHub nach einer neuen Version,
  lädt das passende Paket (Linux/Windows/macOS) im Hintergrund und prüft die SHA-256-Prüfsumme. Danach fragt sie
  „Jetzt neu starten“ oder „Später“ (dann wird beim Beenden installiert). Datenbank, Einstellungen und Backups bleiben;
  die alten Programmdateien werden ersetzt, nicht überschrieben. Schalter und „Jetzt suchen“ unter Einstellungen →
  System & Design. Läuft die App aus dem Quellcode oder ist der Programmordner schreibgeschützt, gibt es nur einen
  Hinweis mit Link zur Download-Seite.
- **`kern.py`** — die Rechenregeln (Feiertage, Tagessoll, Pausen nach ArbZG, Überstunden, Mitternachtsschichten,
  Überschneidungen) ohne PyQt, gemeinsam für Desktop und Server.

### Changed
- `logic.py` importiert die Rechenregeln aus `kern.py` (gleiche Namen, gleiches Verhalten — 28.300 Vergleiche mit der
  bisherigen Qt-Fassung identisch, Desktop-Tests unverändert grün). Feiertage werden je Jahr/Land/Region zwischengespeichert.

### Tests
- `tests/test_kern.py` (Rechenregeln ohne Qt), `tests/test_server_sync.py` (Melden, Rundweg gegen die echte
  Server-Version), `web/tests/test_web.py` (23 Prüfungen der Server-Version). Gegenprobe:
  263 Zufallseinträge, von `MainTab.recalculate_all_days` und der Server-Version gerechnet, auf die Minute gleich.

### Fixed
- **Pylint CI grün** — Pylint schlug mit Exit-Code 28 fehl (Convention+Refactor+Warning). Behoben durch: entfernung ungenutzter Imports, Beseitigung von Duplikat-Keys im i18n-Übersetzungswörterbuch, Zeilenlängen-Korrekturen, `max()`-Builtin statt if-Block, fehlende Docstrings/Final-Newlines, Inline-`pylint: disable` für beabsichtigte Qt-Patterns (CamelCase-Args, unused-arg in Dialog-Init) und Erweiterung der `.pylintrc` um projektweite Disables für GUI-typische Patterns (lazy imports, too-many-locals/statements/lines, duplicate-code, attribute-defined-outside-init u.a.).
- **GitHub Actions Node.js 20 Deprecation** — `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` und `actions/download-artifact` auf Node.js 24-kompatible Versionen (v5/v6) aktualisiert.

---

## [1.8.1] – 2026-07-11

### Fixed
- **Sortierung der Einträge auf der Hauptseite** — Arbeitseinträge am selben Tag wurden innerhalb des Tages nach aufsteigender Startzeit angezeigt statt absteigend. Der neueste Eintrag (späteste Uhrzeit) steht nun ganz oben. Betroffen war `_consolidate_blocks` in `tabs/main_tab.py`: der Sortierschlüssel enthielt nur das Datum, nicht die Uhrzeit.

### Tests
- Neuer Regressionstest `test_eintraege_selber_tag_sortiert_absteigend` (drei Einträge am selben Tag mit unterschiedlichen Uhrzeiten → Anzeige-Reihenfolge absteigend nach Startzeit).

## [1.8.0] – 2026-06-22

### Added
- **Anwesenheits-Tab (Login/Logout-Historie)** — neuer Tab "Anwesenheit" zeigt die vergangenen Tage mit Login- und Logout-Zeit sowie der Anwesenheitsdauer an. Die Zeiten werden aus den System-Protokollen ausgelesen — die App muss dafür nicht laufen. So kann man vergessene Einträge anhand der Anwesenheitszeiten später nachholen.
  - Login- und Logout-Zeiten werden beim App-Start aus `journalctl` (systemd-logind) bzw. `last` ausgelesen und in die Datenbank übernommen.
  - Es werden bis zu 30 Tage zurückliegender Sessions erfasst — auch Tage, an denen die App nicht geöffnet war.
  - Verwaiste Sessions (Shutdown/Crash ohne Logout-Event) werden mit Shutdown-Zeiten aus `last -F reboot` ergänzt.
  - Pro Tag gilt: frühester Login bleibt erhalten, spätester Logout gewinnt.
  - Bei Logout am Folgetag (Nachtschicht) wird die Anwesenheitsdauer korrekt mit +24h berechnet.
  - Monatsfilter und "Aktualisieren"-Button zum Neuladen der Tabelle.
- **System-Session-Erkennung** — neue Funktion `get_system_sessions()` in `logic.py` für plattformübergreifende Login/Logout-Erkennung (Linux: journalctl+last, macOS: last -y, Windows: nicht unterstützt).
- **Datenbank-Migration v3** — `device_login`-Tabelle erhält neue `end_time`-Spalte (Logout-Zeit); bestehende Datenbanken werden automatisch migriert.

### Changed
- `device_login`-Tabelle: bisher nur `start_time` (Login), jetzt auch `end_time` (Logout).
- `set_device_login()` nutzt jetzt UPSERT (`ON CONFLICT DO UPDATE WHERE start_time = ''`), sodass ein Login auch nachträglich eingetragen wird, wenn bereits ein Logout-Eintrag existiert.
- Neue DBManager-Methoden: `set_device_logout()` (Logout speichern/aktualisieren), `load_all_device_logins()` (alle Login/Logout-Einträge laden).
- `_on_data_changed()` aktualisiert jetzt auch den Anwesenheits-Tab.
- DB-Wechsel in Einstellungen: `set_db()` wird auch für den Session-Tab aufgerufen.
- `closeEvent` zeichnet keinen Logout mehr auf — stattdessen werden System-Sessions beim Start synchronisiert.

### Tests
- 9 neue Tests für `device_login`/`set_device_logout`/`load_all_device_logins` (Login/Logout speichern, Überschreiben, Login-nach-Logout, Sortierung, Migration v2→v3).

---

## [1.7.1] – 2026-06-20

### Fixed
- **No settings written while building the Goals tab** — the goal-hours auto-calculation no longer persists settings as a side effect of widget construction. The computed value is now stored on the first regular data refresh instead of during `__init__`.
- **PDF export no longer shadows the stdlib `html` module** — the local HTML string in `export_pdf` was renamed so a later `html.escape()` call in that function cannot silently break.

### Changed
- **Vacation summary placeholder renamed** from `{u}` to `{r}` (remaining) in both the source string and the English catalog, so a translator reordering the placeholders can no longer swap "remaining" and "entitlement".

---

## [1.7.0] – 2026-06-19

### Security
- **Hardcoded Android signing password removed** from `.claude/settings.local.json`. Keystore credentials must live only in the gitignored `android/keystore.properties`, never in the repository.

### Fixed
- **Edit dialog validates overlaps before closing** — editing a work entry into a time range that collides with another entry is now rejected inside the dialog (with a warning) instead of silently discarding the edit after the dialog had already closed.
- **CSV import rejects unparseable dates** — rows whose date matches no known format are skipped instead of being stored verbatim as an invalid date string.
- **Live preview no longer mis-detects absences as duplicates** — the "just saved" marker is only set for work entries (which carry start/end times), so saving an absence and then a work entry with the same widget times is no longer wrongly treated as a duplicate.

### Android
- **Explicit database migrations** — `fallbackToDestructiveMigration()` was removed so a future schema change must ship a real migration instead of silently wiping the user's data.
- **Atomic external-DB import** — data is read in full and then replaced inside a single transaction (`replaceAllEntries`/`replaceAllBereitschaft`); a failed import no longer leaves the local database empty.
- **Minified release builds** — R8 code and resource shrinking is enabled with ProGuard keep rules for Room and Compose.

---

## [1.6.0] – 2026-06-18

### Added
- **Per-weekday work targets** — each weekday (Mon–Sun) gets its own target hours (e.g. shorter Friday); replaces the flat *workdays* + single *target_work_time* model, which remains as fallback for existing settings.
- **Entry types** — entries can be marked as *Work*, *Vacation*, *Sick*, *Holiday*, or *Flextime reduction*. Absence entries correctly neutralize the daily target; flextime entries spend accumulated overtime. A **vacation account** (entitlement vs. used days this year) is shown in the main tab.
- **Monthly PDF report** — new "Monats-PDF (.pdf)" export in the dropdown renders a per-day table with target, balance, running total, and signature lines.
- **Automatic database backups** — a rotating backup is created on every start (last 10 kept) in a `backups/` folder next to the database, using SQLite's consistent backup API. Settings → System & Appearance gains **"Create backup now"** and **"Restore from backup"**.

### Changed
- **Reproducible builds**: `holidays` and `pycountry` are now pinned in `requirements.txt`.
- **Database schema is versioned** via `PRAGMA user_version` with an idempotent migration runner (v0→v1→v2), replacing the ad-hoc "does this column exist" checks.
- Settings → Workdays is now a dedicated **"Arbeitstage"** tab with a per-weekday grid (checkbox + time); the vacation entitlement spinbox lives there too.

### CI
- Release notes are now filled automatically from the matching `CHANGELOG.md` section (no more empty release bodies).

---

## [1.5.0] – 2026-06-18

### Added
- **Automatic theme** — Settings → Appearance now offers **Light / Dark / Automatic (system)**, with *Automatic* as the new default. In automatic mode the app follows the OS color scheme and switches **live** when the system theme changes (no restart). Detection uses Qt's `colorScheme()` style hint with a palette-lightness fallback.

### Changed
- The dark-mode on/off checkbox was replaced by a three-way **Theme** selector; the effective light/dark value (`dark_mode`) is now derived from the selected mode.
- Release artifact filenames now include the version, e.g. `Überzeit-Rechner-1.5.0-linux-x86_64.tar.gz` (Windows `.zip` / macOS `.dmg` accordingly). The version is read from `config.APP_VERSION`.

---

## [1.4.0] – 2026-06-18

### Added
- **"About" window** in Settings → System & Appearance ("Über das Programm" button) showing the app version, a short description, the Python/PyQt6/Qt versions, and the license. The version comes from a single source (`config.APP_VERSION`).

### Fixed
- **Overnight overtime balance corrupted**: a shift ending exactly at `00:00` created a phantom next-day entry that subtracted a full day's target, and a shift crossing midnight (e.g. `22:00–06:00`) had its daily target subtracted twice and its mandatory break dropped. Such shifts are now counted once, correctly.
- **CSV import is now atomic** — if any row fails, the whole batch is rolled back instead of leaving half-imported, un-consolidated entries.
- **Corrupt settings no longer crash startup**: a settings file that is invalid JSON or not a JSON object falls back to defaults; settings are now written atomically (temp file + rename) so an interrupted save can't corrupt them.
- Settings dialog no longer raises on a settings file with incomplete break-rule or special-day entries.
- **PDF export escapes free-text fields** (reason, title), so characters like `<`, `>`, `&` no longer corrupt the exported table.
- Statistics **"⌀ per month"** now divides by the number of calendar months in the period (gaps included) instead of only the months that contain data.
- Statistics **longest plus/minus streak** now counts consecutive calendar days; gaps between recorded days correctly break the streak.
- Goal **"extra minutes per day"** tip rounds up, so the goal is actually reached on the planned date instead of being undershot.
- The welcome wizard's first-run flag is now cleared only when the wizard is completed; cancelling it no longer permanently skips onboarding.

### Changed
- Overnight shifts are stored as a single entry on the start day (consistent with CSV import) instead of being split across two calendar days.

---

## [1.3.1] – 2026-05-29

### Fixed
- **Auto-pause break tier** now follows net working time instead of gross attendance (ArbZG §4): just over 9 h of attendance no longer wrongly triggered the 45-minute mandatory break.

---

## [1.3.0] – 2026-05-19

### Added
- **New "Bereitschaft" tab** for managing on-call (standby) periods — single or multi-day, with optional start/end times and notes
- **Calendar marker for on-call**: continuous colored line drawn in the lower portion of each day cell across the entire on-call period; color configurable in Settings → System & Design
- **"Heute" (Today) button** in the calendar tab for quick navigation back to the current month
- **Statistics tab redesigned**:
  - KPI bar with six metrics: total balance, average per month, best/worst month, longest plus and minus streak
  - Time-period filter (last 12 months / current year / previous year / all)
  - Stock-chart-style cumulative balance curve with month-end markers, segment-wise green/red coloring at zero crossings, and current-balance annotation
  - Monthly bar chart and average-balance-per-weekday chart side by side
  - Warning when entries without dates are present so they don't silently break the cumulative view
- **Login-time-as-start checkbox** added to the welcome wizard; default for new installs is now enabled
- Qt standard dialogs (Yes/No, OK/Cancel) now show in the active app language

### Changed
- Calendar navigation buttons simplified to `<` / `>` arrows
- Calendar grid lines hidden so the on-call line draws seamlessly across day cells
- Holiday cell text color now follows the overtime sign (green/red) instead of a fixed blue
- Statistics "Total balance" KPI always reflects the all-time balance, regardless of the period filter (other KPIs respect the filter)

### Fixed
- Statistics tab balance no longer diverges from the main tab when entries have unusual date formats

---

## [1.2.1] – 2026-05-19

### Fixed
- Overtime sum (saldo) displayed too small in compiled builds — universal `font-size` rule in the QSS overrode `QFont.setPointSize()` on all labels with explicit sizes
- Build script broke when the venv's pyinstaller console script had a stale shebang (e.g. after the repo was moved or renamed); PyInstaller is now invoked via `python -m PyInstaller`

### Changed
- Renamed build artifacts from `Überstundenrechner` to `Überzeit-Rechner` (binary, archive, app-bundle directory)
- Spin-box arrows in compiled builds: thinner, flatter chevrons that sit closer to the center of the field; no separate button background, hover highlights only the arrow in Breeze blue
- Push buttons in compiled builds: hover highlights only the border (no background fill)
- Date pickers in compiled builds: removed the Fusion default contour around the calendar drop-down button

---

## [1.1.0] – 2026-05-18

### Added
- App renamed to **Überzeit Rechner**
- Setup wizard can now be relaunched via Settings → System & Design
- Screenshots added to README
- Sample database (`demo_daten.db`) available as release download
- Placeholder hint in Goals tab when no goal is configured

### Fixed
- Translation: "billable" → "countable" for max work time label
- All Pylint warnings resolved (score 10/10)

---

## [1.0.2] – 2026-05-18

### Added
- First-run welcome dialog for initial configuration (country, region, work hours, workdays)
- Internationalization improvements

---

## [1.0.1] – 2026-05-18

### Changed
- UI arrow icons updated

---

## [1.0.0] – 2026-05-18

### Added
- Initial release
- Time tracking with start/end times and automatic break calculation
- Overtime calculation with configurable daily target
- Calendar heatmap with monthly balance overview
- Monthly statistics chart
- Overtime goal tracker (vacation saver dashboard)
- CSV, Excel (.xlsx) and PDF export
- CSV import
- Dark mode support (Breeze style on Linux, Fusion style in compiled mode)
- Public holiday support for multiple countries and regions
- Midnight shift detection (auto-split across two days)
- Overlap detection with live preview
- Login time detection (Windows, Linux, macOS)
- Configurable special days with reduced targets (e.g. Dec 24)
- Multilingual: German and English
- All data stored locally in SQLite — no cloud, no telemetry
