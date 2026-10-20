"""
Mit dem Rechner starten und im Hintergrund weiterlaufen (Wunsch 20.10.2026).

Die App soll nach der Anmeldung von selbst starten, nur als Symbol in der Taskleiste (Infobereich,
unter macOS die Menüleiste) sitzen und die Anwesenheit an die Server-Version melden. Das Symbol
selbst baut main.py (Qt); hier steht nur der Autostart, ohne Qt und ohne Fremdpakete, damit er sich
testen lässt:

    Windows  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run  (Wert "UeberzeitRechner")
    Linux    ~/.config/autostart/ueberzeit-rechner.desktop       (XDG, GNOME/KDE/XFCE)
    macOS    ~/Library/LaunchAgents/de.bluelight.ueberzeit-rechner.plist

Gestartet wird jeweils mit HINTERGRUND_ARG: dann öffnet sich kein Fenster, nur das Symbol erscheint.
"""
import hashlib
import getpass
import os
import plistlib
import shlex
import subprocess
import sys

HINTERGRUND_ARG = "--hintergrund"
NAME_WINDOWS = "UeberzeitRechner"
RUN_SCHLUESSEL = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME_MAC = "de.bluelight.ueberzeit-rechner"
DATEI_LINUX = "ueberzeit-rechner.desktop"


def startbefehl():
    """Befehl, der diese App im Hintergrund startet (gebautes Paket oder python main.py)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, HINTERGRUND_ARG]
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    return [sys.executable, main_py, HINTERGRUND_ARG]


def _linux_datei():
    basis = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(basis, "autostart", DATEI_LINUX)


def _mac_datei():
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", NAME_MAC + ".plist")


def _windows_befehl(befehl):
    return subprocess.list2cmdline(befehl)


def autostart_aktiv(plattform=None):
    """Ist der Autostart für diese App eingetragen?"""
    plattform = plattform or sys.platform
    if plattform.startswith("win"):
        try:
            import winreg  # pylint: disable=import-outside-toplevel,import-error
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_SCHLUESSEL) as schluessel:
                winreg.QueryValueEx(schluessel, NAME_WINDOWS)
            return True
        except OSError:
            return False
    if plattform == "darwin":
        return os.path.exists(_mac_datei())
    return os.path.exists(_linux_datei())


def autostart_setzen(an, plattform=None, icon=None):
    """Trägt den Autostart ein (an=True) oder entfernt ihn. Fehler gehen als OSError hoch."""
    plattform = plattform or sys.platform
    befehl = startbefehl()
    if plattform.startswith("win"):
        import winreg  # pylint: disable=import-outside-toplevel,import-error
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_SCHLUESSEL, 0,
                            winreg.KEY_SET_VALUE) as schluessel:
            if an:
                winreg.SetValueEx(schluessel, NAME_WINDOWS, 0, winreg.REG_SZ,
                                  _windows_befehl(befehl))
            else:
                try:
                    winreg.DeleteValue(schluessel, NAME_WINDOWS)
                except FileNotFoundError:
                    pass
        return
    datei = _mac_datei() if plattform == "darwin" else _linux_datei()
    if not an:
        if os.path.exists(datei):
            os.remove(datei)
        return
    os.makedirs(os.path.dirname(datei), exist_ok=True)
    if plattform == "darwin":
        with open(datei, "wb") as f:
            # ProcessType Interactive: macOS drosselt die App nicht wie einen Dienst im Hintergrund
            plistlib.dump({"Label": NAME_MAC, "ProgramArguments": befehl, "RunAtLoad": True,
                           "ProcessType": "Interactive"}, f)
        return
    zeilen = ["[Desktop Entry]", "Type=Application", "Name=Überzeit Rechner",
              "Comment=Überstunden erfassen und an den Server melden",
              "Exec=" + " ".join(shlex.quote(t) for t in befehl), "Terminal=false",
              "X-GNOME-Autostart-enabled=true"]
    if icon:
        zeilen.append("Icon=" + icon)
    with open(datei, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")


def instanz_name(basis):
    """Name für eine Einzelinstanz-Sperre: je Benutzer und Installationsordner einer."""
    try:
        wer = getpass.getuser()
    except (KeyError, OSError):
        wer = "user"
    pruef = hashlib.sha1(f"{wer}|{os.path.abspath(basis)}".encode()).hexdigest()[:12]
    return "ueberzeit-rechner-" + pruef
