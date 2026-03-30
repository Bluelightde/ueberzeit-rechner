#!/usr/bin/env python3
"""
Build-Skript für den Überstundenrechner.
Läuft auf Linux, macOS und Windows.

Verwendung:
    python build.py [--no-package]

Optionen:
    --no-package   Nur kompilieren, kein ZIP / DMG erzeugen
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
APP_NAME    = "Überstundenrechner"
SPEC_FILE   = "ueberstunden.spec"
DIST_DIR    = Path("dist")
BUILD_DIR   = Path("build")
SCRIPT_DIR  = Path(__file__).parent.resolve()

PLAT        = sys.platform          # 'linux', 'darwin', 'win32'
ARCH        = platform.machine()    # 'x86_64', 'arm64', …


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print('='*60)


def run(*args, **kwargs):
    """Führt einen Befehl aus und bricht bei Fehler ab."""
    cmd = [str(a) for a in args]
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"\n[FEHLER] Befehl fehlgeschlagen (Exit {result.returncode})")
        sys.exit(result.returncode)
    return result


def find_python() -> Path:
    """Gibt den Python-Interpreter im venv zurück, falls vorhanden."""
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
    # Fallback: System-Python
    return Path(sys.executable)


def find_pyinstaller(python: Path) -> list:
    """Gibt den PyInstaller-Aufruf als Liste zurück."""
    if PLAT == "win32":
        pi = python.parent / "pyinstaller.exe"
    else:
        pi = python.parent / "pyinstaller"
    if pi.exists():
        return [str(pi)]
    print("\n[FEHLER] pyinstaller-Binary nicht gefunden nach Installation.")
    print("  Bitte manuell ausführen:")
    print(f"  {python} -m pip install --force-reinstall pyinstaller")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Build-Schritte
# ---------------------------------------------------------------------------

def install_deps(python: Path):
    step("Abhängigkeiten installieren")
    # sicherstellen, dass pip selbst verfügbar ist
    run(python, "-m", "ensurepip", "--upgrade")
    req = SCRIPT_DIR / "requirements.txt"
    if req.exists():
        run(python, "-m", "pip", "install", "-r", str(req), "--upgrade")
    else:
        print("  requirements.txt nicht gefunden – übersprungen.")

    # Prüfen ob pyinstaller-Binary vorhanden ist.
    # Kann fehlen wenn das venv ursprünglich mit einer anderen Python-Version
    # erstellt wurde (Scripts werden dann nicht in bin/ angelegt).
    if PLAT == "win32":
        pi_bin = python.parent / "pyinstaller.exe"
    else:
        pi_bin = python.parent / "pyinstaller"
    if not pi_bin.exists():
        print("  pyinstaller-Binary fehlt – erzwinge Neuinstallation …")
        run(python, "-m", "pip", "install", "--force-reinstall", "pyinstaller")


def clean_old_build():
    step("Altes Build-Verzeichnis bereinigen")
    for d in [DIST_DIR / APP_NAME, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Gelöscht: {d}")


def run_pyinstaller(python: Path):
    step("PyInstaller starten")
    pi_cmd = find_pyinstaller(python)
    run(*pi_cmd, str(SCRIPT_DIR / SPEC_FILE), cwd=str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Paketierung
# ---------------------------------------------------------------------------

def package_linux():
    step("Linux: tar.gz erstellen")
    src = DIST_DIR / APP_NAME
    if not src.exists():
        print(f"  [WARNUNG] {src} nicht gefunden – übersprungen.")
        return
    out_name = f"{APP_NAME}-linux-{ARCH}.tar.gz"
    out_path = DIST_DIR / out_name
    import tarfile
    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(src, arcname=APP_NAME)
    print(f"  Paket erstellt: {out_path}  ({out_path.stat().st_size // 1024} KB)")


def package_windows():
    step("Windows: ZIP erstellen")
    src = DIST_DIR / APP_NAME
    if not src.exists():
        print(f"  [WARNUNG] {src} nicht gefunden – übersprungen.")
        return
    out_name = f"{APP_NAME}-windows-{ARCH}.zip"
    out_path = DIST_DIR / out_name
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            zf.write(file, Path(APP_NAME) / file.relative_to(src))
    print(f"  Paket erstellt: {out_path}  ({out_path.stat().st_size // 1024} KB)")


def package_macos():
    step("macOS: DMG erstellen")
    app_path = DIST_DIR / f"{APP_NAME}.app"
    if not app_path.exists():
        print(f"  [WARNUNG] {app_path} nicht gefunden – übersprungen.")
        return

    out_name = f"{APP_NAME}-macos-{ARCH}.dmg"
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
        out_name = f"{APP_NAME}-macos-{ARCH}.zip"
        out_path = DIST_DIR / out_name
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in app_path.rglob("*"):
                zf.write(file, Path(f"{APP_NAME}.app") / file.relative_to(app_path))
        print(f"  hdiutil nicht gefunden – ZIP erstellt: {out_path}")


# ---------------------------------------------------------------------------
# Ergebnis-Zusammenfassung
# ---------------------------------------------------------------------------

def summary():
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
    parser = argparse.ArgumentParser(
        description="Baut den Überstundenrechner für die aktuelle Plattform.")
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
