# Changelog

All notable changes to Überzeit Rechner are documented here.

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
