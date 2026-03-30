# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Überstunden-Rechner** is a German overtime tracking desktop application built with Python, PyQt6, and SQLite. It runs as a single-file application (`ueberstunden.py`).

## Running the Application

```bash
# Activate the venv first
source venv/bin/activate  # bash/zsh
source venv/bin/activate.fish  # fish

# Run the application
python ueberstunden.py
```

## Building a Distributable (PyInstaller)

```bash
source venv/bin/activate
pyinstaller --onefile --windowed --add-data "icon.png:." ueberstunden.py
```

The output binary will be in `dist/`. On macOS, `BASE_DIR` is resolved 4 levels up from `sys.executable` inside the `.app` bundle so that `ueberstunden_daten.db` and `ueberstunden_settings.json` are stored next to the app, not inside it.

## Installing / Updating Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Dependencies: `PyQt6`, `matplotlib`, `pyinstaller`.

## Architecture

The entire application lives in `ueberstunden.py` (~1240 lines). It is structured in clearly marked sections (`# --- ... ---`):

1. **Configuration & Paths** — PyInstaller-compatible `BASE_DIR`/`BUNDLE_DIR` detection; paths for `DB_FILE`, `SETTINGS_FILE`, `ICON_PATH`.
2. **Data class** — `WorkEntry` dataclass (id, date, start, end, pause, minutes, reason).
3. **Holiday calculator** — `get_holidays(year, state)` computes all German public holidays for a given federal state using the Gaussian Easter algorithm plus state-specific rules.
4. **`DBManager`** — Thin SQLite wrapper (one table: `entries`). Methods: `load_all`, `insert`, `update`, `delete`, `get_last_entry_before`.
5. **Business logic** — `calculate_work_details(start, end, target_minutes)` computes gross time, auto-pause (0/30/45 min per German law), net time (capped at 600 min/10 h), and overtime delta.
6. **`HeatmapDelegate`** — `QStyledItemDelegate` that draws a blue border on the calendar cell for today.
7. **Dialogs** — `SettingsDialog` (default start time, target work time, federal state, dark mode) and `EditDialog` (edit/create a `WorkEntry` with live recalculation).
8. **`UeberstundenApp`** — `QMainWindow` with four tabs:
   - *Eingabe & Liste*: time entry form + filterable table with edit/delete.
   - *Ziele & Dashboard*: overtime goal tracker with progress bar and estimated daily required overtime.
   - *Kalender-Heatmap*: monthly calendar grid coloured by overtime intensity; highlights holidays and today.
   - *Diagramm & Statistik*: matplotlib bar chart (weekly overtime) + aggregate stats.

## Persistent Storage

- `ueberstunden_daten.db` — SQLite database (next to the script / executable).
- `ueberstunden_settings.json` — JSON settings file. Keys: `default_start`, `default_end`, `target_work_time`, `state`, `dark_mode`, `goal_active`, `goal_start_date`, `goal_end_date`, `goal_hours`, `goal_date`, `last_date`, `last_start`.

## Theme Handling

- In compiled mode (`sys.frozen`): always uses Fusion style; applies a full `QPalette` for dark/light.
- In script mode on Linux: uses `Breeze` style; dark mode defers to the system palette.
- Theme is applied once at startup via `apply_theme()`; changing dark mode in settings requires a restart.
