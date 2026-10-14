
"""
Geschäftslogik zur Feiertagsberechnung, Zeitauswertung und Login-Ermittlung.
Enthält außerdem gemeinsam genutzte Hilfsfunktionen für alle Tab-Widgets.
"""
import getpass
import logging
import re
import subprocess
import sys
from PyQt6.QtCore import QDate, QLocale, QTime
from i18n import get_locale
# Rechenregeln ohne Qt liegen in kern.py (gemeinsam mit der Server-Version web/);
# hier unter den bisherigen Namen weiter angeboten.
# pylint: disable=unused-import
from kern import (  # noqa: F401
    ABSENCE_TYPES, ALL_TYPES, DEFAULT_BREAK_RULES, TYPE_FLEXTIME, TYPE_HOLIDAY, TYPE_LABELS,
    TYPE_PARENTAL, TYPE_SICK, TYPE_VACATION, TYPE_WORK, calculate_timed_entries,
    format_time, get_absence_minutes, get_holidays, get_max_minutes, get_target_minutes,
    get_target_minutes_for_date, is_midnight_shift, split_midnight_shift,
)

logger = logging.getLogger(__name__)


# pylint: disable=too-many-locals, too-many-branches


# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_linux():
    """Linux-spezifische Ermittlung der Login-Zeit."""
    user = getpass.getuser()
    # 1. Versuch: Frühester Login von HEUTE
    try:
        r = subprocess.run(
            ["journalctl", "-u", "systemd-logind",
             "--grep", f"New session.*{user}",
             "--since", "today", "--output=short-iso", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False
        )
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                if "New session" in line and user in line:
                    m = re.search(r"T(\d{2}):(\d{2}):", line)
                    if m:
                        return QTime(int(m.group(1)), int(m.group(2)))
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("journalctl (today) fehlgeschlagen: %s", exc)

    # 2. Versuch: Letzter Login überhaupt (Fallback wie bisher)
    try:
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
        logger.debug("journalctl (last) fehlgeschlagen, versuche 'who': %s", exc)

    # Fallback: who
    try:
        r = subprocess.run(["who"], capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0:
            logins = []
            for line in r.stdout.strip().splitlines():
                if line.startswith(user + " ") or line.startswith(user + "\t"):
                    m = re.search(r"(\d{2}:\d{2})", line)
                    if m:
                        logins.append(QTime.fromString(m.group(1), "HH:mm"))
            if logins:
                return min(logins)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'who'-Abfrage (Linux) fehlgeschlagen: %s", exc)
    return None

# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_darwin():
    """macOS-spezifische Ermittlung der Login-Zeit."""
    user = getpass.getuser()
    try:
        # last -y zeigt das Jahr, LC_ALL=C für stabiles Datumsformat
        r = subprocess.run(["last", "-y", user], env={"LC_ALL": "C"},
                           capture_output=True, text=True, timeout=5, check=False)
        if r.returncode == 0 and r.stdout:
            # "ddd MMM d" in English locale (e.g. "Thu Apr 2")
            en_locale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
            today_prefix = en_locale.toString(QDate.currentDate(), "ddd MMM d")
            logins_today = []
            all_logins = []
            for line in r.stdout.splitlines():
                if not line.strip() or "wtmp begins" in line:
                    continue
                m = re.search(r"\s(\d{1,2}:\d{2})\s", line)
                if m:
                    t = QTime.fromString(m.group(1).zfill(5), "HH:mm")
                    all_logins.append(t)
                    if today_prefix in line:
                        logins_today.append(t)

            if logins_today:
                return min(logins_today)
            if all_logins:
                return all_logins[0] # 'last' ist absteigend sortiert, also neuester
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'last'-Abfrage (macOS) fehlgeschlagen, versuche 'who': %s", exc)

    # Fallback: who
    try:
        r = subprocess.run(["who"], capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0:
            logins = []
            for line in r.stdout.strip().splitlines():
                if line.startswith(user):
                    m = re.search(r"(\d{1,2}:\d{2})", line)
                    if m:
                        logins.append(QTime.fromString(m.group(1).zfill(5), "HH:mm"))
            if logins:
                return min(logins)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'who'-Abfrage (macOS) fehlgeschlagen: %s", exc)
    return None

# pylint: disable=too-many-locals, too-many-branches
def _get_login_time_win32():
    """Windows-spezifische Ermittlung der Login-Zeit."""
    _no_win = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        # PowerShell-Script: Sucht alle Logins (LogonType 2=Interactive, 10=RemoteInteractive),
        # filtert auf HEUTE und nimmt den ersten (frühesten).
        # Falls heute keiner, nimm den allerletzten verfügbaren.
        ps_cmd = (
            "$today = (Get-Date).Date; "
            "$logons = Get-CimInstance Win32_LogonSession | "
            "Where-Object {$_.LogonType -in 2,10} | Sort-Object StartTime; "
            "$today_logons = $logons | Where-Object {$_.StartTime -ge $today}; "
            "if ($today_logons) { $today_logons[0].StartTime.ToString('HH:mm') } "
            "else { ($logons | Select-Object -Last 1).StartTime.ToString('HH:mm') }"
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


# --- Eintragstypen (#1) ---


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


# pylint: disable=too-many-locals, too-many-branches
def _get_system_sessions_linux():
    """Linux-spezifische Ermittlung aller Login/Logout-Sessions.

    Liest aus journalctl (systemd-logind):
      - 'New session N of user X with class user' → Login
      - 'Session N logged out'                     → Logout
    Verwaiste Sessions (Shutdown ohne Logout-Event) werden mit
    `last -F reboot` End-Zeiten ergänzt.

    Rückgabe: Liste von Dicts {"date", "login", "logout"}.
    """
    user = getpass.getuser()
    sessions = {}  # session_nr → {"date", "login"}
    results = []

    try:
        r = subprocess.run(
            ["journalctl", "-u", "systemd-logind",
             "--grep", "New session|logged out",
             "--since", "30 days ago",
             "--output=short-iso", "--no-pager"],
            capture_output=True, text=True, timeout=10, check=False
        )
        if r.returncode != 0:
            return []

        for line in r.stdout.strip().splitlines():
            m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", line)
            if not m:
                continue
            date_str = m.group(1)
            time_str = m.group(2)

            # Neu: "New session '3' of user 'miw' with class 'user'"
            # Alt: "New session 3 of user miw."
            # Nur class 'user' zählt (nicht 'manager'/'greeter'/'manager-early')
            m_login_new = re.search(
                r"New session '(\d+)' of user '(\S+)' with class '(\w+)'", line)
            m_login_old = re.search(
                r"New session (\d+) of user (\S+)\.", line)
            if m_login_new:
                if m_login_new.group(2) == user and m_login_new.group(3) == "user":
                    sess_nr = m_login_new.group(1)
                    sessions[sess_nr] = {"date": date_str, "login": time_str}
                    continue
            elif m_login_old:
                if m_login_old.group(2) == user:
                    sess_nr = m_login_old.group(1)
                    sessions[sess_nr] = {"date": date_str, "login": time_str}
                    continue

            m_logout = re.search(r"Session (\d+) logged out", line)
            if m_logout:
                sess_nr = m_logout.group(1)
                if sess_nr in sessions:
                    sessions[sess_nr]["logout"] = time_str
                    results.append(sessions.pop(sess_nr))
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("journalctl (sessions) fehlgeschlagen: %s", exc)

    # Verwaiste Sessions (kein 'logged out' → Shutdown/Crash):
    # Logout aus `last -F reboot` End-Zeit ermitteln.
    if sessions:
        shutdowns = _get_reboot_end_times_linux()
        for sess_nr, info in list(sessions.items()):
            logout = _find_shutdown_after(shutdowns, info["date"], info["login"])
            if logout:
                info["logout"] = logout
                results.append(info)
                del sessions[sess_nr]
        # Verbleibende ohne Shutdown-Zeit → zumindest Login speichern
        for info in sessions.values():
            results.append(info)

    # Nach Datum/Zeit sortieren, Duplikate pro Tag zusammenführen
    return _merge_sessions(results)


def _get_reboot_end_times_linux():
    """Liest Shutdown-Zeiten aus `last -F reboot`.

    Rückgabe: Liste von (date_str, time_str) – Boot-Ende = Shutdown.
    """
    shutdowns = []
    try:
        r = subprocess.run(["last", "-F", "reboot"],
                           capture_output=True, text=True, timeout=5, check=False)
        if r.returncode != 0:
            return shutdowns
        # C-Locale für stabiles Datumsformat
        c_locale = QLocale(QLocale.Language.C)
        fmt = "ddd MMM d HH:mm:ss yyyy"
        for line in r.stdout.splitlines():
            if "wtmp begins" in line or not line.strip():
                continue
            if "still running" in line:
                continue
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            # Format: "reboot system boot KERNEL Day Mon D HH:MM:SS YYYY
            #          - Day Mon D HH:MM:SS YYYY (duration)"
            m = re.search(
                r"-\s+(\w{3}\s+\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\d{4})", line)
            if m:
                dt = c_locale.toDateTime(m.group(1), fmt)
                if dt.isValid():
                    shutdowns.append((
                        dt.date().toString("yyyy-MM-dd"),
                        dt.time().toString("HH:mm"),
                    ))
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'last -F reboot' fehlgeschlagen: %s", exc)
    return shutdowns


def _find_shutdown_after(shutdowns, date_str, login_time):
    """Findet die erste Shutdown-Zeit nach dem gegebenen Login."""
    for sd_date, sd_time in shutdowns:
        if sd_date > date_str or (sd_date == date_str and sd_time > login_time):
            return sd_time
    return None


def _get_system_sessions_darwin():
    """macOS-spezifische Ermittlung aller Login/Logout-Sessions via `last -y`.

    Rückgabe: Liste von Dicts {"date", "login", "logout"}.
    """
    user = getpass.getuser()
    results = []
    try:
        r = subprocess.run(["last", "-y", user], env={"LC_ALL": "C"},
                           capture_output=True, text=True, timeout=5, check=False)
        if r.returncode != 0:
            return []
        c_locale = QLocale(QLocale.Language.C)
        fmt = "ddd MMM d HH:mm yyyy"
        for line in r.stdout.splitlines():
            if "wtmp begins" in line or not line.strip():
                continue
            # Format: "user ttys000  Mon Jun 22 06:58 - 17:30  (10:32)"
            # oder "user ttys000  Mon Jun 22 06:58 - still logged in"
            m = re.search(
                r"(\w{3}\s+\w{3}\s+\d+\s+\d{2}:\d{2})\s+-\s+(\d{2}:\d{2}|still logged in)",
                line)
            if not m:
                continue
            login_dt = c_locale.toDateTime(m.group(1), fmt)
            if not login_dt.isValid():
                continue
            date_str = login_dt.date().toString("yyyy-MM-dd")
            login_str = login_dt.time().toString("HH:mm")
            logout_str = ""
            if m.group(2) != "still logged in":
                logout_str = m.group(2)
            results.append({"date": date_str, "login": login_str,
                             "logout": logout_str})
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("'last -y' (sessions) fehlgeschlagen: %s", exc)
    return _merge_sessions(results)


def _merge_sessions(sessions):
    """Führt mehrere Sessions pro Tag zusammen.

    Pro Tag: frühester Login + spätester Logout.
    """
    by_date = {}
    for s in sessions:
        d = s["date"]
        if d not in by_date:
            by_date[d] = {"date": d, "login": s["login"], "logout": s.get("logout", "")}
        else:
            existing = by_date[d]
            if s["login"] and (not existing["login"] or s["login"] < existing["login"]):
                existing["login"] = s["login"]
            if s.get("logout", "") and s["logout"] > existing["logout"]:
                existing["logout"] = s["logout"]
    return sorted(by_date.values(), key=lambda s: s["date"], reverse=True)


def get_system_sessions():
    """Ermittelt alle Login/Logout-Sessions des aktuellen Benutzers aus dem System.

    Die Daten werden aus den System-Protokollen ausgelesen (nicht aus der App)
    und können vergangene Tage abdecken, an denen die App nicht lief.

    Linux  : journalctl (systemd-logind), Shutdown aus `last -F reboot`
    macOS  : last -y
    Windows: nicht unterstützt (braucht Admin-Rechte für Event Log)

    Rückgabe: Liste von Dicts {"date": "yyyy-MM-dd", "login": "HH:mm",
              "logout": "HH:mm" oder ""}.
    """
    if sys.platform.startswith("linux"):
        return _get_system_sessions_linux()
    if sys.platform == "darwin":
        return _get_system_sessions_darwin()
    return []
