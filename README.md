# Überstunden-Rechner Pro

Ein leistungsstarker, lokal laufender Überstunden-Rechner mit grafischer Benutzeroberfläche (PyQt6), der dir hilft, deine Arbeitszeiten, Pausen und Überstunden präzise zu erfassen und zu visualisieren.

## ✨ Funktionen

- **Präzise Zeiterfassung**: Erfasse Start- und Endzeiten sowie Pausen. Manuelle Korrekturbuchungen sind ebenfalls möglich.
- **Flexibles Tagessoll**:
    - **Individuelles Tagessoll pro Eintrag**: Überschreibe das Soll direkt bei der Eingabe für einen spezifischen Tag.
    - **Sonder-Arbeitstage**: Definiere wiederkehrende Tage mit reduziertem Soll (z.B. Heiligabend und Silvester mit je 4h) in den Einstellungen.
    - **Regelarbeitszeit**: Hinterlege dein Standard-Soll für normale Arbeitstage.
- **Intelligente Feiertags- & Wochenendlogik**: 
    - Berücksichtigt alle gesetzlichen Feiertage in Deutschland (nach Bundesland einstellbar).
    - **Konfigurierbare Arbeitstage**: Wähle deine regulären Arbeitstage (z.B. Mo-Fr). 
    - **Überstunden-Automatik**: Arbeit an freien Tagen, Wochenenden oder Feiertagen wird automatisch zu 100% als Überstunden gewertet (Soll = 0).
- **Automatische Pausenberechnung**: Berechnet gesetzliche Pausenzeiten automatisch (30 Min ab 6h, 45 Min ab 9h Arbeitszeit).
- **Login-Zeit Erkennung**: Kann optional die letzte Anmeldezeit des Betriebssystems (Windows, Linux, macOS) als Standard-Startzeit vorschlagen.
- **Visualisierungen**:
    - **Kalender-Heatmap**: Farblich kodierte Übersicht deines Monats-Saldos. Wochenenden und freie Tage werden hervorgehoben.
    - **Statistik-Diagramme**: Monatlicher Verlauf deiner Überstunden.
- **Gleitzeit-Ziel (Dashboard)**: Setze dir Ziele (z.B. Stunden für einen Urlaub ansparen) und verfolge den Fortschritt. Die Berechnung berücksichtigt automatisch Feiertage und deine konfigurierten Arbeitstage.
- **Dark Mode**: Unterstützung für helles und dunkles Design (Breeze Theme).
- **Daten-Export**: Exportiere deine Daten als CSV, Excel (.xlsx) oder PDF.
- **Datenschutz**: Alle Daten werden lokal in einer SQLite-Datenbank (`ueberstunden_daten.db`) gespeichert. Keine Cloud, kein Tracking.

## 🚀 Installation

### Voraussetzungen
- Python 3.8 oder neuer

### Repository klonen & Abhängigkeiten installieren
1. Klone das Repository:
   ```bash
   git clone https://github.com/dein-nutzername/ueberstundenrechner.git
   cd ueberstundenrechner
   ```

2. Erstelle eine virtuelle Umgebung (empfohlen):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Unter Windows: venv\Scripts\activate
   ```

3. Installiere die benötigten Pakete:
   ```bash
   pip install -r requirements.txt
   ```

## 🛠️ Benutzung

Starte die Anwendung mit:
```bash
python ueberstunden.py
```

### Erste Schritte
1. Gehe auf **Einstellungen**.
2. Wähle dein **Bundesland** aus (wichtig für die korrekte Feiertagsberechnung).
3. Lege deine **Regelarbeitszeit (Soll)** und deine regulären **Arbeitstage** fest.
4. Definiere unter **Sonder-Arbeitstage** Tage mit abweichendem Soll (z.B. 24.12. und 31.12.).
5. (Optional) Aktiviere den **Dark Mode** oder die **Login-Zeit Erkennung**.

## 📦 Kompilieren (Executable erstellen)

Du kannst die Anwendung mit PyInstaller zu einer eigenständigen Datei kompilieren:
```bash
pyinstaller ueberstunden.spec
```
Die fertige Anwendung findest du anschließend im Ordner `dist/`.

## 📜 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert. Siehe die `LICENSE`-Datei für Details.
