# Changelog

All notable changes to Überzeit Rechner are documented here.

---

## [Unreleased]

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
