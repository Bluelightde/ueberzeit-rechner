#!/usr/bin/env python3
"""
Build-Skript für den Überzeit-Rechner.
Läuft auf Linux, macOS und Windows.

Verwendung:
    python build.py [--no-package]

Optionen:
    --no-package   Nur kompilieren, kein ZIP / DMG erzeugen
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
APP_NAME    = "Überzeit-Rechner"
SPEC_FILE   = "ueberstunden.spec"
DIST_DIR    = Path("dist")
BUILD_DIR   = Path("build")
SCRIPT_DIR  = Path(__file__).parent.resolve()

PLAT        = sys.platform          # 'linux', 'darwin', 'win32'
ARCH        = platform.machine()    # 'x86_64', 'arm64', …


def _read_app_version() -> str:
    """Liest APP_VERSION aus config.py, OHNE das Modul zu importieren
    (config.py zieht Laufzeit-Abhängigkeiten, die bei der Build-Orchestrierung
    – System-Python in der CI – evtl. noch nicht installiert sind)."""
    try:
        text = (SCRIPT_DIR / "config.py").read_text(encoding="utf-8")
        match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


APP_VERSION = _read_app_version()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def step(msg: str):
    """Gibt einen formatierten Fortschrittsschritt aus."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print('='*60)


def run(*args, **kwargs):
    """Führt einen Befehl aus und bricht bei Fehler ab."""
    cmd = [str(a) for a in args]
    print(f"  $ {' '.join(cmd)}")
    # We handle the error manually below, so we set check=False if not provided.
    if 'check' not in kwargs:
        kwargs['check'] = False
    result = subprocess.run(cmd, **kwargs)  # pylint: disable=subprocess-run-check
    if result.returncode != 0:
        print(f"\n[FEHLER] Befehl fehlgeschlagen (Exit {result.returncode})")
        sys.exit(result.returncode)
    return result


def create_venv():
    """Legt ein frisches venv an, falls noch keines existiert."""
    venv_dir = SCRIPT_DIR / "venv"
    if venv_dir.exists():
        return
    step("Virtuelles Environment anlegen")
    print(f"  $ {sys.executable} -m venv {venv_dir}")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=False,
    )
    if result.returncode != 0:
        print("\n[FEHLER] venv konnte nicht erstellt werden.")
        sys.exit(result.returncode)
    print("  venv erstellt.")


def find_python() -> Path:
    """Gibt den Python-Interpreter im venv zurück; legt das venv vorher an falls nötig."""
    create_venv()
    if PLAT == "win32":
        candidates = [
            SCRIPT_DIR / "venv" / "Scripts" / "python.exe",
            SCRIPT_DIR / "venv" / "Scripts" / "python3.exe",
        ]
    else:
        candidates = [
            SCRIPT_DIR / "venv" / "bin" / "python",
            SCRIPT_DIR / "venv" / "bin" / "python3",
        ]
    for c in candidates:
        if c.exists():
            return c
    print("\n[FEHLER] Python-Interpreter im venv nicht gefunden.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Build-Schritte
# ---------------------------------------------------------------------------

def install_deps(python: Path):
    """Installiert die Abhängigkeiten aus der requirements.txt."""
    step("Abhängigkeiten installieren")
    req = SCRIPT_DIR / "requirements.txt"
    if req.exists():
        run(python, "-m", "pip", "install", "-r", str(req), "--upgrade")
    else:
        print("  requirements.txt nicht gefunden – übersprungen.")



def clean_old_build():
    """Löscht alte Build- und Dist-Verzeichnisse."""
    step("Altes Build-Verzeichnis bereinigen")
    for d in [DIST_DIR / APP_NAME, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Gelöscht: {d}")


def run_pyinstaller(python: Path):
    """Führt PyInstaller aus, um die Anwendung zu bauen."""
    step("PyInstaller starten")
    # Aufruf via `python -m PyInstaller` statt des pyinstaller-Wrappers,
    # damit eine ggf. kaputte Shebang-Zeile im venv (z.B. nach Umbenennen
    # des Repo-Verzeichnisses) den Build nicht blockiert.
    run(python, "-m", "PyInstaller", str(SCRIPT_DIR / SPEC_FILE),
        cwd=str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Paketierung
# ---------------------------------------------------------------------------

def package_linux():
    """Erstellt ein tar.gz-Paket für Linux."""
    step("Linux: tar.gz erstellen")
    src = DIST_DIR / APP_NAME
    if not src.exists():
        print(f"  [WARNUNG] {src} nicht gefunden – übersprungen.")
        return
    out_name = f"{APP_NAME}-{APP_VERSION}-linux-{ARCH}.tar.gz"
    out_path = DIST_DIR / out_name
    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(src, arcname=APP_NAME)
    print(f"  Paket erstellt: {out_path}  ({out_path.stat().st_size // 1024} KB)")


def package_windows():
    """Erstellt ein ZIP-Paket für Windows."""
    step("Windows: ZIP erstellen")
    src = DIST_DIR / APP_NAME
    if not src.exists():
        print(f"  [WARNUNG] {src} nicht gefunden – übersprungen.")
        return
    out_name = f"{APP_NAME}-{APP_VERSION}-windows-{ARCH}.zip"
    out_path = DIST_DIR / out_name
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            zf.write(file, Path(APP_NAME) / file.relative_to(src))
    print(f"  Paket erstellt: {out_path}  ({out_path.stat().st_size // 1024} KB)")


def package_macos():
    """Erstellt ein DMG- oder ZIP-Paket für macOS."""
    app_path = DIST_DIR / f"{APP_NAME}.app"
    if not app_path.exists():
        print(f"  [WARNUNG] {app_path} nicht gefunden – übersprungen.")
        return

    out_name = f"{APP_NAME}-{APP_VERSION}-macos-{ARCH}.dmg"
    out_path = DIST_DIR / out_name

    # hdiutil ist auf jedem Mac vorhanden
    if shutil.which("hdiutil"):
        # Temporäres DMG aus dem dist-Ordner
        run("hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", str(app_path),
            "-ov", "-format", "UDZO",
            str(out_path))
        print(f"  Paket erstellt: {out_path}")
    else:
        # Fallback: ZIP des .app-Bundles
        out_name = f"{APP_NAME}-{APP_VERSION}-macos-{ARCH}.zip"
        out_path = DIST_DIR / out_name
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in app_path.rglob("*"):
                zf.write(file, Path(f"{APP_NAME}.app") / file.relative_to(app_path))
        print(f"  hdiutil nicht gefunden – ZIP erstellt: {out_path}")


# ---------------------------------------------------------------------------
# Ergebnis-Zusammenfassung
# ---------------------------------------------------------------------------

def summary():
    """Gibt eine Zusammenfassung der erstellten Dateien aus."""
    step("Build abgeschlossen")
    print(f"  Plattform : {PLAT} / {ARCH}")
    print(f"  Ausgabe   : {(SCRIPT_DIR / DIST_DIR).resolve()}")
    print()
    for f in sorted(DIST_DIR.rglob("*")):
        if f.is_file() and f.suffix in (".gz", ".zip", ".dmg", ".exe", ""):
            size_kb = f.stat().st_size // 1024
            print(f"    {f.relative_to(DIST_DIR)}  ({size_kb} KB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Haupteinstiegspunkt für das Build-Skript."""
    parser = argparse.ArgumentParser(
        description="Baut den Überzeit-Rechner für die aktuelle Plattform.")
    parser.add_argument("--no-package", action="store_true",
                        help="Kein ZIP/DMG erzeugen, nur kompilieren")
    args = parser.parse_args()

    os.chdir(SCRIPT_DIR)

    python = find_python()
    print(f"\nPython-Interpreter : {python}")
    print(f"Ziel-Plattform     : {PLAT} / {ARCH}")

    install_deps(python)
    clean_old_build()
    run_pyinstaller(python)

    if not args.no_package:
        if PLAT == "darwin":
            package_macos()
        elif PLAT == "win32":
            package_windows()
        else:
            package_linux()

    summary()


if __name__ == "__main__":
    main()
