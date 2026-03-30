# Überstunden-Rechner Pro

Eine Desktop-Anwendung zur Erfassung und Auswertung von Überstunden, gebaut mit Python, PyQt6 und SQLite.

---

## Starten

```bash
# Virtuelle Umgebung aktivieren
source venv/bin/activate        # bash/zsh
source venv/bin/activate.fish   # fish

# Anwendung starten
python ueberstunden.py
```

---

## Funktionsübersicht

### Tab 1 – Eingabe & Liste

**Zeiterfassung**
- Datum, Start- und Endzeit sowie einen Anlass eingeben und mit **Eintragen** speichern.
- **Jetzt**-Schaltflächen setzen die aktuelle Uhrzeit direkt als Start- oder Endzeit.
- Die **Live-Vorschau** zeigt sofort Netto-Arbeitszeit, Pause und das Tages-Überstundensaldo.
- Das **Gesamt-Saldo** (alle Einträge) wird oben groß angezeigt, farblich grün (Plus) oder rot (Minus).

**Automatische Pausenberechnung**
- Bei aktivierter Auto-Pause (Standard) wird die Pause nach deutschem Arbeitszeitgesetz automatisch berechnet:
  - Ab 6 Std. Arbeitszeit: 30 Min. Pause
  - Ab 9 Std. Arbeitszeit: 45 Min. Pause
- Pausen werden tagesübergreifend korrekt auf mehrere Einträge verteilt.

**Überschneidungsprüfung**
- Beim Eintragen und beim Bearbeiten wird geprüft, ob sich der neue Zeitraum mit einem bestehenden Eintrag desselben Tages überschneidet. Bei Konflikt erscheint eine Warnung.

**Ruhezeit-Warnung**
- Die Live-Vorschau warnt, wenn die Ruhezeit zum vorherigen Arbeitstag weniger als 11 Stunden beträgt.

**Eintrags-Liste**
- Alle Einträge werden in einer Tabelle mit Datum, Zeitraum, Überstunden und Anlass angezeigt.
- Per **Doppelklick** auf eine Zeile öffnet sich der Bearbeitungsdialog.
- Einträge können über den **Löschen**-Button entfernt werden (mit Bestätigungsdialog).
- Nach jeder Änderung werden alle Einträge des betroffenen Tages automatisch neu berechnet.

**Monatsfilter**
- Die Liste kann nach einem bestimmten Monat gefiltert werden. Der Filter wirkt sich auch auf den Export und die Kalenderansicht aus.

**Manuelle Einträge (ohne Zeiten)**
- Einträge können auch ohne Start-/Endzeit angelegt werden (z. B. für manuelle Korrekturen oder Urlaub). Diese werden in der Tagesberechnung separat als Korrekturbetrag berücksichtigt.

---

### Mehrere Einträge an einem Tag

Es können beliebig viele Einträge für denselben Tag angelegt werden, z. B. wenn jemand einen Einsatz mit Unterbrechung hat oder vormittags und nachmittags separat erfasst.

**Zusammenrechnung**

Alle Zeiteinträge des Tages (mit Start- und Endzeit) werden gemeinsam ausgewertet:

1. Die Einträge werden nach Startzeit sortiert.
2. Die **Brutto-Arbeitszeit** aller Einträge wird aufaddiert.
3. **Lücken zwischen den Einträgen** (z. B. 12:00–13:00 Pause zwischen zwei Blöcken) werden automatisch als Unterbrechungszeit erkannt und bei der Pausenberechnung angerechnet.

**Pausenverteilung (Auto-Modus)**

Die gesetzlich vorgeschriebene Gesamtpause wird auf die Einträge des Tages verteilt:
- Die Lücken zwischen den Einträgen werden zuerst als Pause angerechnet.
- Reichen die Lücken nicht aus, wird die fehlende Restpause dem **letzten Eintrag** des Tages zugerechnet.
- So ergibt sich für jeden Einzeleintrag ein realistischer Pausenwert, der in der Liste angezeigt wird.

**Überstunden-Zuweisung**

Die Überstunden des gesamten Tages (Netto-Arbeitszeit minus Regelarbeitszeit) werden immer **nur dem letzten Eintrag** (nach Startzeit) gutgeschrieben. Alle früheren Einträge desselben Tages erhalten 0 Minuten. Das stellt sicher, dass das Tages-Saldo nur einmal gezählt wird.

**Automatische Neuberechnung**

Wird ein Eintrag hinzugefügt, bearbeitet oder gelöscht, berechnet die App alle Einträge des betroffenen Tages automatisch neu und speichert die aktualisierten Pausen- und Überstunden-Werte in der Datenbank.

**Überschneidungsprüfung**

Bevor ein Eintrag gespeichert wird, prüft die App, ob sich der angegebene Zeitraum mit einem bereits vorhandenen Eintrag desselben Tages überschneidet. Bei einer Überschneidung erscheint eine Warnung mit dem betroffenen Eintrag, und der neue Eintrag wird **nicht** gespeichert.

**Manuelle Einträge im Mix**

Manuelle Einträge (ohne Start-/Endzeit) desselben Tages werden nicht in die Zeitberechnung einbezogen, aber ihr Minuten-Wert wird zum Tages-Saldo addiert. Das erlaubt z. B. eine manuelle Korrektur neben normalen Zeitbuchungen.

**Beispiel**

| Eintrag | Start | Ende | Brutto | Lücke davor | Pause (auto) | Netto | Überstunden |
|---------|-------|------|--------|-------------|--------------|-------|-------------|
| Vormittag | 07:00 | 12:00 | 5h | – | 0 min | 5h | 0 min |
| Nachmittag | 13:00 | 17:00 | 4h | 60 min (als Pause angerechnet) | 0 min | 4h | +1h |

Gesamt: 9h Brutto, 60 min Lücke → 8h Netto, Regelarbeitszeit 8h → **0 Überstunden**
(Die 60-Minuten-Lücke deckt die gesetzlich vorgeschriebene 30-Minuten-Pause ab; da 9h > 6h gilt die 30-Minuten-Regel.)

---

### Tab 2 – Ziele & Dashboard

**Gleitzeit-Ziel (Urlaubs-Sparer)**
- Ein Überstunden-Ziel für einen zukünftigen Zeitraum (z. B. Urlaub) kann aktiviert werden.
- Start- und Enddatum des Urlaubszeitraums eingeben; die benötigten Stunden werden automatisch aus der Anzahl der Arbeitstage (ohne Wochenenden und Feiertage) und der eingestellten Regelarbeitszeit berechnet.
- Der Stundenwert kann manuell überschrieben werden.

**Fortschritts-Dashboard**
- Zeigt den aktuellen Überstunden-Stand, die noch fehlenden Stunden und die verbleibenden Arbeitstage bis zum Zieldatum.
- Ein **Fortschrittsbalken** visualisiert den Zielerreichungsgrad in Prozent.
- Ein **Tipp** berechnet, wie viele Minuten täglich zusätzlich gearbeitet werden müssen, um das Ziel pünktlich zu erreichen.
- Bei erreichtem Ziel erscheint eine Glückwunsch-Meldung.

---

### Tab 3 – Kalender-Heatmap

- Monatliche Kalenderansicht, in der jeder Tag farblich nach dem Überstunden-Saldo eingefärbt ist:
  - **Grün** (intensiver je mehr Plus-Stunden)
  - **Rot** (intensiver je mehr Minus-Stunden)
  - **Blau** = Feiertag ohne gebuchte Stunden
  - **Dunkelblau mit weißem Rahmen** = heutiger Tag
- Feiertage werden mit ihrem Namen angezeigt (bundeslandspezifisch).
- Oben rechts steht das **Monats-Saldo** für den angezeigten Monat.
- Navigation per Dropdown oder den Schaltflächen **< Vorheriger** / **Nächster >**.
- Der Kalenderfilter ist mit dem Monatsfilter im ersten Tab synchronisiert.

---

### Tab 4 – Diagramm & Statistik

- **Balkendiagramm** des monatlichen Überstunden-Verlaufs:
  - Grüne Balken = Plus-Monate
  - Rote Balken = Minus-Monate
- Das Diagramm passt sich dem Dark/Light-Mode der Anwendung an.

---

## Import & Export

### CSV-Import
- Bestehende Daten können aus einer CSV-Datei importiert werden.
- Unterstützte Spalten: `Datum`, `Minuten`, `Anlass`, `Start`, `Ende`, `Pause`
- Datumsformate: `TT.MM.JJ`, `TT.MM.JJJJ` oder `JJJJ-MM-TT`
- Trennzeichen `;` oder `,` werden automatisch erkannt.
- Vor dem Import wird eine Vorschau angezeigt; es wird automatisch ein Datenbank-Backup angelegt (`ueberstunden_daten.db.backup`).
- Überstunden und Pausen werden nach dem Import für alle betroffenen Tage neu berechnet.

### Export
Über den **Export**-Button in der Toolbar stehen drei Formate zur Verfügung:

| Format | Inhalt |
|--------|--------|
| **CSV** | Tabelle mit Datum, Zeitraum, Minuten, Dauer, Anlass und Gesamtsumme |
| **Excel (.xlsx)** | Formatierte Tabelle mit farbiger Kopfzeile, abwechselnden Zeilen, farbiger Überstundenspalte und Summenzeile (benötigt `openpyxl`) |
| **PDF** | Druckfertige Tabelle als PDF-Datei |

Der Export berücksichtigt den aktuell aktiven Monatsfilter (Alle oder ein bestimmter Monat).

---

## Einstellungen

Erreichbar über den **Einstellungen**-Button. Folgende Parameter sind konfigurierbar:

| Einstellung | Beschreibung |
|-------------|--------------|
| **Login-Zeit als Startzeit** | Liest beim Programmstart die letzte Anmeldezeit des Benutzers aus (Linux via journalctl/who, macOS via last/who, Windows via PowerShell). Die konfigurierte Startzeit dient als Fallback. |
| **Fallback Startzeit** | Standard-Startzeit, wenn keine Login-Zeit verfügbar ist |
| **Regelarbeitszeit (Soll)** | Tägliche Soll-Arbeitszeit (z. B. 08:00 für 8 Stunden) |
| **Max. anrechenbare Arbeitszeit** | Obergrenze für die täglich angerechnete Arbeitszeit (Standard: 10 h) |
| **Automatische Pausenberechnung** | An: Pausen nach ArbZG; Aus: manuelle Eingabe der Pause |
| **Bundesland** | Bestimmt, welche gesetzlichen Feiertage in Kalender und Zielberechnung berücksichtigt werden (alle 16 Bundesländer) |
| **Dark Mode** | Schaltet zwischen hellem und dunklem Theme um (erfordert Neustart) |

---

## Datenhaltung

| Datei | Inhalt |
|-------|--------|
| `ueberstunden_daten.db` | SQLite-Datenbank mit allen Einträgen |
| `ueberstunden_settings.json` | Gespeicherte Einstellungen |

Beide Dateien liegen neben der Skript- bzw. Executable-Datei.

---

## Abhängigkeiten installieren

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Pflicht: `PyQt6`, `matplotlib`
Optional: `openpyxl` (für Excel-Export)
Build: `pyinstaller`

---

## Distributable bauen (PyInstaller)

```bash
source venv/bin/activate
pyinstaller --onefile --windowed --add-data "icon.png:." ueberstunden.py
```

Das fertige Binary liegt in `dist/`.
