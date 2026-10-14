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
- `kern.py` — Qt-free calculation rules (holidays, daily target, ArbZG breaks, overtime, overlaps, midnight shifts). Shared by the desktop app and the server version — change rules here, never duplicate them.
- `server_sync.py` — Qt-free: sends the attendance (`device_login`) to the server version with a device token (`POST /api/geraet/anwesenheit`); called from `main.py` at start and every 30 min in a background thread. Settings keys `server_sync`, `server_url`, `server_token`.
- `updater.py` — Qt-free self-update from GitHub releases (`releases/latest`): picks the package for this OS, downloads it to `<BASE_DIR>/.update/`, verifies GitHub's SHA-256 `digest`, unpacks to `.update/neu/` and swaps the program files on exit (old ones to `.update/alt/`; db/settings/backups stay). Linux/macOS swap in-process, Windows via a generated `update.cmd` that waits for the PID. `main.py` checks 8 s after start and every 6 h in a background thread (setting `update_auto`, default on), asks “Jetzt neu starten / Später”, stores `update_erwartet` to report success/failure on the next start. Only frozen builds with a writable folder install themselves; otherwise it just links the release page.
- `logic.py` — Re-exports the rules from `kern.py` plus Qt helpers (date/time formatting, OS login/session detection).
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
- `ueberstunden_settings.json` — JSON settings file. Keys include: `default_start`, `target_work_time`, `state`, `theme` (`light`/`dark`/`auto`; the effective `dark_mode` bool is derived from it), `goal_active`, `goal_start_date`, `goal_end_date`, `goal_hours`, `goal_date`, `last_date`, `last_start`.

## Theme Handling

- In compiled mode (`sys.frozen`): always uses Fusion style; applies a full `QPalette` for dark/light.
- In script mode on Linux: uses `Breeze` style; dark mode defers to the system palette.
- The `theme` setting is `light`, `dark`, or `auto` (default). `apply_theme()` resolves it to an effective `dark_mode` bool — via `QStyleHints.colorScheme()` with a palette-lightness fallback — and stamps `settings['dark_mode']` (read by the calendar/stats tabs). In `auto` mode the app follows the OS scheme **live** via the `colorSchemeChanged` signal; manual changes apply immediately through `apply_theme()`. No restart needed.

## Server Version (`web/`)

Flask app in `web/` (browser + installable PWA, one data set per user, OIDC login). It imports `kern.py` and `models.py`
from the repo root; Docker builds from the root (`compose.yml`, `web/Dockerfile`). Tests:
`python -m unittest discover -s web/tests`. Details in `web/README.md`. The desktop app does not depend on `web/`.
