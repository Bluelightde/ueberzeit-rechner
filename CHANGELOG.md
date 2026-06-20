# Changelog

All notable changes to Überzeit Rechner are documented here.

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
