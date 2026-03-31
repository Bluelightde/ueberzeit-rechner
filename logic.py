
"""
Geschäftslogik zur Feiertagsberechnung, Zeitauswertung und Login-Ermittlung.
Enthält außerdem gemeinsam genutzte Hilfsfunktionen für alle Tab-Widgets.
"""
import getpass
import logging
import re
import subprocess
import sys
import holidays as holidays_lib
from PyQt6.QtCore import QDate, QLocale, QTime
from i18n import get_locale

logger = logging.getLogger(__name__)


def get_holidays(year, country, subdiv=None):
    """Gibt gesetzliche Feiertage als {yyyy-MM-dd: name} zurück.

    Nutzt die holidays-Bibliothek für internationale Unterstützung.
    country: ISO 3166-1 Alpha-2 Code (z.B. 'DE', 'FR', 'US')
    subdiv:  Regions-/Bundeslandcode (z.B. 'TH' für Thüringen), oder None
    """
    try:
        h = holidays_lib.country_holidays(country, subdiv=subdiv, years=year)
        return {d.strftime("%Y-%m-%d"): name for d, name in h.items()}
    except (KeyError, NotImplementedError) as exc:
        logger.warning("Feiertage für %s/%s konnten nicht geladen werden: %s",
                       country, subdiv, exc)
        return {}

# pylint: disable=too-many-locals, too-many-branches
DEFAULT_BREAK_RULES = [
    {"after": 360, "break": 30},   # >6h → 30 Min (deutsches ArbZG)
    {"after": 540, "break": 45},   # >9h → 45 Min (deutsches ArbZG)
]


def calculate_timed_entries(timed_entries, target_mins, max_mins, is_auto, break_rules=None):
    """Berechnet Pause und Überstunden für die Zeiteinträge eines Tages.

    Gibt ein Tupel (results, total_net) zurück:
      results    — dict {entry.id: (pause_min, overtime_min)}
      total_net  — tatsächliche Netto-Arbeitszeit des Tages (nach Cap) in Minuten

    break_rules — Liste von {"after": Minuten, "break": Minuten}, nach "after" absteigend
                  geprüft. None verwendet DEFAULT_BREAK_RULES (deutsches ArbZG).
    Nur der letzte Eintrag nach Startzeit erhält die Überstunden; alle anderen 0.
    Manuelle Einträge (ohne Start-/Endzeit) werden nicht übergeben und bleiben unberührt.
    """
    rules = sorted(
        break_rules if break_rules is not None else DEFAULT_BREAK_RULES,
        key=lambda r: r["after"], reverse=True
    )
    sorted_entries = sorted(timed_entries, key=lambda x: x.start or "00:00")
    results = {}
    total_accumulated_gross = 0
    total_accumulated_gap = 0
    recorded_pause_distributed = 0
    last_end_qtime = None

    for i, e in enumerate(sorted_entries):
        current_gross = 0
        if e.start and e.end:
            try:
                s = QTime.fromString(e.start, "HH:mm")
                en = QTime.fromString(e.end, "HH:mm")
                diff = s.secsTo(en) // 60
                if diff < 0:
                    diff += 24 * 60
                current_gross = diff
                if last_end_qtime:
                    gap = last_end_qtime.secsTo(s) // 60
                    if gap < 0:
                        gap += 24 * 60
                    total_accumulated_gap += max(0, gap)
                last_end_qtime = en
            except (ValueError, TypeError) as exc:
                logger.warning("Ungültige Zeitdaten in Eintrag %s, wird übersprungen: %s",
                               e.id, exc)

        total_accumulated_gross += current_gross

        if is_auto:
            req = 0
            for rule in rules:
                if total_accumulated_gross > rule["after"]:
                    req = rule["break"]
                    break
            current_total_pause_needed = max(0, req - total_accumulated_gap)
            current_break = max(0, current_total_pause_needed - recorded_pause_distributed)
        else:
            current_break = e.pause

        if i == len(sorted_entries) - 1:
            total_net = total_accumulated_gross - (recorded_pause_distributed + current_break)
            ovt = int(min(max_mins, total_net) - target_mins)
        else:
            ovt = 0

        results[e.id] = (int(current_break), ovt)
        recorded_pause_distributed += current_break

    total_net = min(max_mins, total_accumulated_gross - recorded_pause_distributed)
    return results, total_net

# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_linux():
    """Linux-spezifische Ermittlung der Login-Zeit."""
    # Primär: journalctl mit --output=short-iso für zuverlässiges Parsing
    try:
        user = getpass.getuser()
        r = subprocess.run(
            ["journalctl", "-u", "systemd-logind",
             "--grep", f"New session.*{user}",
             "-n", "1", "--output=short-iso", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False
        )
        if r.returncode == 0 and r.stdout.strip():
            m = re.search(r"T(\d{2}):(\d{2}):", r.stdout.strip().split("\n")[-1])
            if m:
                return QTime(int(m.group(1)), int(m.group(2)))
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("journalctl-Abfrage fehlgeschlagen, versuche 'who': %s", exc)

    # Fallback: who
    try:
        user = getpass.getuser()
        r = subprocess.run(["who"], capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                if line.startswith(user + " ") or line.startswith(user + "\t"):
                    m = re.search(r"(\d{2}:\d{2})", line)
                    if m:
                        return QTime.fromString(m.group(1), "HH:mm")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'who'-Abfrage (Linux) fehlgeschlagen: %s", exc)
    return None

# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_darwin():
    """macOS-spezifische Ermittlung der Login-Zeit."""
    try:
        user = getpass.getuser()
        r = subprocess.run(["last", "-1", user],
                           capture_output=True, text=True, timeout=5, check=False)
        if r.returncode == 0 and r.stdout:
            m = re.search(r"\s(\d{1,2}:\d{2})\s", r.stdout.split("\n")[0])
            if m:
                return QTime.fromString(m.group(1).zfill(5), "HH:mm")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'last'-Abfrage (macOS) fehlgeschlagen, versuche 'who': %s", exc)

    # Fallback: who
    try:
        user = getpass.getuser()
        r = subprocess.run(["who"], capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                if line.startswith(user):
                    m = re.search(r"(\d{1,2}:\d{2})", line)
                    if m:
                        return QTime.fromString(m.group(1).zfill(5), "HH:mm")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'who'-Abfrage (macOS) fehlgeschlagen: %s", exc)
    return None

# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_win32():
    """Windows-spezifische Ermittlung der Login-Zeit."""
    _no_win = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        ps_cmd = (
            "(Get-CimInstance Win32_LogonSession | "
            "Where-Object {$_.LogonType -in 2,10} | "
            "Sort-Object StartTime -Descending | "
            "Select-Object -First 1).StartTime.ToString('HH:mm')"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=8, check=False, **_no_win
        )
        if r.returncode == 0 and r.stdout.strip():
            return QTime.fromString(r.stdout.strip(), "HH:mm")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("PowerShell-Abfrage (Windows) fehlgeschlagen: %s", exc)
    return None

# --- Semantische Farbkonstanten (UI-übergreifend) ---
COLOR_POSITIVE = "#10b981"  # Grün: Überstunden / positiver Saldo
COLOR_NEGATIVE = "#ef4444"  # Rot:  Minus / negativer Saldo
COLOR_INFO     = "#3b82f6"  # Blau: Hinweise / Tipps


def fmt_date(date_str: str) -> str:
    """Konvertiert yyyy-MM-dd in das lokale Kurzformat (z.B. 03/15/24 oder 15.03.24)."""
    d = QDate.fromString(date_str, "yyyy-MM-dd")
    if not d.isValid():
        return date_str
    return get_locale().toString(d, QLocale.FormatType.ShortFormat)


def fmt_time_hhmm(time_str: str) -> str:
    """Konvertiert HH:mm in das lokale Kurzformat (z.B. 2:30 PM oder 14:30)."""
    t = QTime.fromString(time_str, "HH:mm")
    if not t.isValid():
        return time_str
    return get_locale().toString(t, QLocale.FormatType.ShortFormat)


def format_time(total_minutes, show_plus=False):
    """Formatiert Minuten in lesbare Zeitangabe.
    Unter 60 Min → '45m', ab 60 Min → '1h 5m'.
    """
    sign = "+" if show_plus and total_minutes > 0 else ("-" if total_minutes < 0 else "")
    abs_m = abs(total_minutes)
    if abs_m < 60:
        return f"{sign}{abs_m}m"
    return f"{sign}{abs_m // 60}h {abs_m % 60}m"


def get_target_minutes(settings):
    """Gibt die Regelarbeitszeit aus den Einstellungen in Minuten zurück."""
    t = QTime.fromString(settings.get("target_work_time", "08:00"), "HH:mm")
    return t.hour() * 60 + t.minute()


def get_max_minutes(settings):
    """Gibt die maximal anrechenbare Arbeitszeit pro Tag in Minuten zurück."""
    return settings.get("max_work_hours", 10) * 60


def get_target_minutes_for_date(date_str, entries, settings):
    """Ermittelt das Tagessoll für ein bestimmtes Datum.

    Prüft in dieser Reihenfolge:
    1. Individuelles Tagessoll eines vorhandenen Eintrags
    2. Sonderarbeitstage aus den Einstellungen (z.B. 24.12.)
    3. Feiertag → 0 Minuten
    4. Kein Arbeitstag (Wochenende) → 0 Minuten
    5. Reguläre Regelarbeitszeit
    """
    for e in entries:
        if e.date == date_str and e.target_minutes != -1:
            return e.target_minutes

    qdate = QDate.fromString(date_str, "yyyy-MM-dd")

    special_days = settings.get("special_days", [])
    for sd in special_days:
        if qdate.month() == sd["month"] and qdate.day() == sd["day"]:
            t = QTime.fromString(sd["target"], "HH:mm")
            return t.hour() * 60 + t.minute()

    year = qdate.year()
    country = settings.get("country", "DE")
    subdiv = settings.get("state")
    holidays = get_holidays(year, country, subdiv)

    if date_str in holidays:
        return 0

    day_idx = qdate.dayOfWeek() - 1
    workdays = settings.get("workdays", [0, 1, 2, 3, 4])
    if day_idx not in workdays:
        return 0

    return get_target_minutes(settings)


def get_login_time():
    """Ermittelt die letzte Anmeldezeit des aktuellen Benutzers als QTime.
    Gibt None zurück wenn die Zeit nicht ermittelt werden kann.

    Linux  : journalctl (systemd-logind), Fallback: who
    macOS  : last, Fallback: who
    Windows: PowerShell (Win32_LogonSession)
    """
    if sys.platform.startswith("linux"):
        return _get_login_time_linux()
    if sys.platform == "darwin":
        return _get_login_time_darwin()
    if sys.platform == "win32":
        return _get_login_time_win32()
    return None
