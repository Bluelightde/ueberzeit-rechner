# Code-Review: Überstunden-Rechner Pro

## Gesamtbewertung: 7.5 / 10

Ein solides, funktionsreiches Desktop-Programm mit guter Basis. Die Architektur wurde offensichtlich bereits einmal refaktoriert (von einer Monodatei auf Module aufgeteilt). Es gibt klare Stärken, aber auch strukturelle Schwächen, die bei Weiterentwicklung zunehmend hinderlich werden.

---

## Architektur & Struktur

### Stärken

- Die Aufteilung in `models.py`, `database.py`, `logic.py`, `config.py` und `dialogs.py` ist sauber — echte Trennung von Concerns
- Tab-Mixins (`MainTabMixin`, `GoalsTabMixin` usw.) vermeiden Monolithik in der Hauptklasse
- `WorkEntry` als Dataclass ist idiomatisch und klar
- `DBManager` kapselt alle Datenbankzugriffe an einem Ort
- `config.py` mit PyInstaller-kompatiblem Pfad-Handling ist professionell gelöst

### Schwäche — Mixin-Architektur

Das größte strukturelle Problem. Alle Mixins greifen auf `self.entries`, `self.settings`, `self.db` usw. zu — also auf den Zustand der Hauptklasse. Das ist **implizite Kopplung**: ein Mixin funktioniert nur wenn es in `UeberstundenApp` eingebettet ist. Das ist kein echtes Mixin-Muster, sondern eher zerstückelte Klassen.

```python
# In MainTabMixin — greift auf self.settings zu,
# das nur in UeberstundenApp existiert
target_work_time = self.parent().settings.get("target_work_time", "08:00")
```

Besser wäre es, die Tabs als eigenständige `QWidget`-Klassen zu bauen, denen benötigte Daten per Signal/Slot oder Konstruktor übergeben werden.

---

## Code-Qualität

### Stärken

- Durchgängig deutsche Docstrings, konsequent
- Pylint 10.00/10 — keine ungelösten Warnungen
- Keine Magic Numbers ohne Kontext (meist)
- `calculate_timed_entries()` ist algorithmisch durchdacht und korrekt kommentiert

### Schwäche — Funktionsgröße

Mehrere Methoden sind extrem lang. `setup_main_tab()` und `update_main_list()` überschreiten 100–200 Zeilen. Das ist der Hauptgrund für die vielen `# pylint: disable=too-many-locals` Kommentare — die eigentlich ein Symptom sind, kein Problem an sich.

### Schwäche — Stylesheet-Bloat

`main.py` enthält ~400 Zeilen hardcodiertes CSS als Python-String. Das macht die Datei mit 739 Zeilen schon sehr groß. CSS könnte in eine externe `.qss`-Datei ausgelagert werden.

### Schwäche — Redundanz

```python
# goals_tab.py und main_tab.py haben beide:
def format_time(self, minutes): ...
```

`format_time` ist eine reine Utility-Funktion, die mehrfach vorkommt. Gehört in `logic.py` oder eine `utils.py`.

### Schwäche — Fehlende Typisierung

`database.py`, `logic.py` und `dialogs.py` haben kaum Type Hints. `WorkEntry` als Dataclass hat sie, der Rest nicht. Für ein Projekt dieser Größe wären vollständige Annotations sehr hilfreich.

---

## Funktionalität

### Stärken

- Automatische Pausenberechnung nach deutschem Arbeitszeitgesetz (6h → 30 min, 9h → 45 min) ist korrekt implementiert
- Feiertage für alle 16 Bundesländer via Gauss-Algorithmus — vollständig und akkurat
- Login-Zeit-Erkennung auf Linux (journalctl + who), macOS (last), Windows (PowerShell) — gut durchdacht
- Überlappungsprüfung bei Zeiteinträgen
- Export nach CSV, Excel und PDF
- Kalender-Heatmap mit Farbkodierung
- Sonderarbeitstage (z.B. 24.12.) konfigurierbar

### Schwäche — Kein echtes Fehler-Logging

Fehler werden mit `pass` oder `print()` behandelt. Bei einem Desktop-Tool wäre `logging` mit einer Log-Datei sinnvoll, besonders wenn die App kompiliert ausgeliefert wird und der Benutzer keinen Terminal sieht.

```python
# Aktuell überall so:
except (subprocess.SubprocessError, OSError):
    pass
```

### Schwäche — Datenbank-Migration begrenzt

`database.py` hat einfache `ALTER TABLE` Migrationen, aber kein versioniertes Schema. Bei zukünftigen Änderungen kann das problematisch werden.

### Schwäche — Kein Undo

Das Löschen von Einträgen ist nicht rückgängig zu machen. Ein einfacher Bestätigungsdialog existiert zwar, aber kein Undo-Stack.

---

## Tests

**Keine Tests vorhanden.** Das ist die größte Lücke für ein Projekt dieser Komplexität. Gerade `calculate_timed_entries()` und `get_holidays()` sind komplexe Funktionen, die sich hervorragend für Unit-Tests eignen würden:

```python
# Beispiel was fehlt:
def test_auto_break_over_9h():
    # 10h Arbeitszeit → 45 min Pause
    ...

def test_holiday_th_weltkindertag():
    holidays = get_holidays(2024, "TH")
    assert "2024-09-20" in holidays
```

Die CI/CD-Pipeline prüft nur Codequalität (pylint), aber keine korrekte Funktionsweise.

---

## CI/CD & Build

### Stärken

- GitHub Actions mit Matrix-Testing (3.9, 3.10, 3.11)
- `fail-fast: false` verhindert, dass ein fehlgeschlagener Job die anderen abbricht
- `build.py` ist ein professionelles plattformübergreifendes Build-Skript
- `create_icon.py` generiert alle Icon-Formate programmatisch — reproduzierbar

### Verbesserungspotenzial

- `requirements.txt` hat keine gepinnten Versionen (`PyQt6` statt `PyQt6==6.7.0`). Das kann zu unerwarteten Fehlern bei neuen Releases führen
- Kein Release-Workflow (automatisches Erstellen von GitHub Releases / Binaries bei Tags)

---

## Bewertungsübersicht

| Bereich          | Bewertung |
|------------------|-----------|
| Architektur      | 6 / 10    |
| Code-Qualität    | 8 / 10    |
| Funktionalität   | 9 / 10    |
| Tests            | 1 / 10    |
| CI/CD & Build    | 7 / 10    |
| Dokumentation    | 8 / 10    |
| **Gesamt**       | **7.5 / 10** |

---

## Prioritäten für Verbesserungen

1. **Unit-Tests** für `logic.py` und `database.py` einführen
2. **Tabs als eigenständige Widgets** statt Mixins refaktorieren
3. **`format_time` und andere Duplikate** in Hilfsfunktionen zusammenführen
4. **Versionen in `requirements.txt` pinnen**
5. **Logging** statt `pass`/`print` bei Fehlern einsetzen

Das Programm ist für den Eigengebrauch sehr gut. Für eine breitere Veröffentlichung oder Teamarbeit wären Tests und die Mixin-Entkopplung die wichtigsten nächsten Schritte.
