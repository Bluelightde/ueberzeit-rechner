
"""
Geschäftslogik zur Feiertagsberechnung, Zeitauswertung und Login-Ermittlung.
"""
import getpass
import re
import subprocess
import sys
from PyQt6.QtCore import QDate, QTime

def get_holidays(year, state):
    """
    Berechnet die gesetzlichen Feiertage für ein gegebenes Jahr und Bundesland.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = QDate(year, month, day)

    holidays = {
        f"{year}-01-01": "Neujahr",
        easter.addDays(-2).toString("yyyy-MM-dd"): "Karfreitag",
        easter.addDays(1).toString("yyyy-MM-dd"): "Ostermontag",
        f"{year}-05-01": "Tag der Arbeit",
        easter.addDays(39).toString("yyyy-MM-dd"): "Christi Himmelfahrt",
        easter.addDays(50).toString("yyyy-MM-dd"): "Pfingstmontag",
        f"{year}-10-03": "Tag d. Dt. Einheit",
        f"{year}-12-25": "1. Weihnachtstag",
        f"{year}-12-26": "2. Weihnachtstag",
    }

    if state in ["BW", "BY", "ST"]:
        holidays[f"{year}-01-06"] = "Hl. Drei Könige"
    if state in ["BE", "MV"]:
        holidays[f"{year}-03-08"] = "Int. Frauentag"
    if state in ["BW", "HE", "NW", "RP", "SL"] or (state == "BY"):
        holidays[easter.addDays(60).toString("yyyy-MM-dd")] = "Fronleichnam"
    if state in ["BY", "SL"]:
        holidays[f"{year}-08-15"] = "Mariä Himmelfahrt"
    if state == "TH":
        holidays[f"{year}-09-20"] = "Weltkindertag"
    if state in ["BB", "HB", "HH", "MV", "NI", "SH", "SN", "ST", "TH"]:
        holidays[f"{year}-10-31"] = "Reformationstag"
    if state in ["BW", "BY", "NW", "RP", "SL"]:
        holidays[f"{year}-11-01"] = "Allerheiligen"
    if state == "SN":
        d = QDate(year, 11, 22)
        while d.dayOfWeek() != 3:
            d = d.addDays(-1)
        holidays[d.toString("yyyy-MM-dd")] = "Buß- und Bettag"

    return holidays

# pylint: disable=too-many-local-variables, too-many-branches
def calculate_timed_entries(timed_entries, target_mins, max_mins, is_auto):
    """Berechnet Pause und Überstunden für die Zeiteinträge eines Tages.

    Gibt ein Tupel (results, total_net) zurück:
      results   — dict {entry.id: (pause_min, overtime_min)}
      total_net — tatsächliche Netto-Arbeitszeit des Tages (nach Cap) in Minuten

    Nur der letzte Eintrag nach Startzeit erhält die Überstunden; alle anderen 0.
    Manuelle Einträge (ohne Start-/Endzeit) werden nicht übergeben und bleiben unberührt.
    """
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
            except (ValueError, TypeError):
                pass

        total_accumulated_gross += current_gross

        if is_auto:
            if total_accumulated_gross > 9 * 60:
                req = 45
            elif total_accumulated_gross > 6 * 60:
                req = 30
            else:
                req = 0
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

# pylint: disable=too-many-local-variables, too-many-branches
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
    except (subprocess.SubprocessError, OSError):
        pass

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
    except (subprocess.SubprocessError, OSError):
        pass
    return None

# pylint: disable=too-many-local-variables, too-many-branches
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
    except (subprocess.SubprocessError, OSError):
        pass

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
    except (subprocess.SubprocessError, OSError):
        pass
    return None

# pylint: disable=too-many-local-variables, too-many-branches
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
    except (subprocess.SubprocessError, OSError):
        pass
    return None

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
