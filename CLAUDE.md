# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Überstunden-Rechner** is a German overtime tracking desktop application built with Python, PyQt6, and SQLite. It is structured as a modular application with `main.py` as the entry point.

## Running the Application

```bash
# Activate the venv first
source venv/bin/activate  # bash/zsh
source venv/bin/activate.fish  # fish

# Run the application
python main.py
```

## Building a Distributable (PyInstaller)

```bash
python build.py
```
Or manually:
```bash
source venv/bin/activate
pyinstaller ueberstunden.spec
```

The output binary will be in `dist/`.

## Installing / Updating Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Dependencies: `PyQt6`, `matplotlib`, `pyinstaller`, `openpyxl`, `Pillow`, `holidays`, `pycountry`.

## Architecture

The application is modularized into several components:

- `main.py` — Entry point, initializes the application and main window (`UeberstundenApp`).
- `logic.py` — Core business logic for work time calculations (net time, pauses, overtime).
- `database.py` — SQLite database management (`DBManager`).
- `models.py` — Data structures (e.g., `WorkEntry`).
- `config.py` — Global configuration, paths, and constants.
- `i18n.py` — Internationalization support.
- `ui_components.py` — Custom UI widgets and delegates.
- `dialogs.py` — Settings and entry edit dialogs.
- `exports.py` — CSV, Excel, and PDF export functionality.
- `tabs/` — Contains individual tab implementations:
  - `main_tab.py` — Data entry and list view.
  - `goals_tab.py` — Overtime goals and dashboard.
  - `calendar_tab.py` — Calendar heatmap visualization.
  - `stats_tab.py` — Statistics and charts.

## Persistent Storage

- `ueberstunden_daten.db` — SQLite database (next to the script / executable).
- `ueberstunden_settings.json` — JSON settings file. Keys: `default_start`, `default_end`, `target_work_time`, `state`, `dark_mode`, `goal_active`, `goal_start_date`, `goal_end_date`, `goal_hours`, `goal_date`, `last_date`, `last_start`.

## Theme Handling

- In compiled mode (`sys.frozen`): always uses Fusion style; applies a full `QPalette` for dark/light.
- In script mode on Linux: uses `Breeze` style; dark mode defers to the system palette.
- Theme is applied once at startup via `apply_theme()`; changing dark mode in settings requires a restart.
