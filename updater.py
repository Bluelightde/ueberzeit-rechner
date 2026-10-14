"""
Selbst-Aktualisierung über die GitHub-Releases.

Ablauf (main.py ruft das im Hintergrund-Thread auf, ohne Qt):

1. ``suchen()`` fragt ``releases/latest`` ab und wählt das Paket für dieses System
   (``…-linux-x86_64.tar.gz``, ``…-windows-AMD64.zip``, ``…-macos-arm64.dmg``).
2. ``herunterladen()`` lädt es nach ``<BASE_DIR>/.update/`` und prüft die SHA-256-Prüfsumme,
   die GitHub zu jedem Paket angibt. Ohne passende Prüfsumme wird nichts installiert.
3. ``auspacken()`` packt es nach ``.update/neu/`` aus. Darin liegen nur die Programmdateien
   (Programm + ``_internal``, unter macOS die ``.app``).
4. ``installieren()`` beim Beenden: die gleichnamigen alten Programmdateien wandern nach
   ``.update/alt/``, die neuen an ihre Stelle. Datenbank, Einstellungen, Backups und Protokoll
   liegen im selben Ordner, gehören aber nicht zum Paket und bleiben unberührt.
   Linux/macOS tauschen sofort (laufende Dateien dürfen umbenannt werden), Windows sperrt
   laufende Dateien – dort tauscht ein kleines Hilfsskript, sobald das Programm beendet ist.

Selbst installieren geht nur im gebauten Programm (PyInstaller) und nur, wenn der Programmordner
beschreibbar ist. Sonst meldet die App die neue Version nur und verweist auf die Release-Seite.
"""
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile

from netz import ssl_kontext

logger = logging.getLogger(__name__)

REPO = "Bluelightde/ueberzeit-rechner"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_SEITE = f"https://github.com/{REPO}/releases/latest"
WARTEZEIT = 15      # Sekunden für die Abfrage; der Download selbst darf länger dauern
BLOCK = 256 * 1024

NEU, ALT = "neu", "alt"
KEIN_PAKET = "Für dieses System gibt es kein fertiges Paket."


class UpdateFehler(Exception):
    """Verständliche Fehlermeldung für Protokoll und Hinweis."""


# --- Version und Paket ---------------------------------------------------------------------

def version_tupel(text):
    """'v1.10.2' -> (1, 10, 2). Anhänge wie '-rc1' zählen nicht."""
    treffer = re.match(r"v?(\d+(?:\.\d+)*)", (text or "").strip())
    return tuple(int(t) for t in treffer.group(1).split(".")) if treffer else ()


def ist_neuer(neu, alt):
    """True, wenn Version ``neu`` nach ``alt`` kommt (fehlende Stellen zählen als 0)."""
    a, b = version_tupel(neu), version_tupel(alt)
    if not a:
        return False
    laenge = max(len(a), len(b))
    return a + (0,) * (laenge - len(a)) > b + (0,) * (laenge - len(b))


def plattform():
    """(system, architektur) wie build.py die Pakete benennt, z. B. ('windows', 'amd64')."""
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    return system, platform.machine().lower()


def paket_waehlen(assets, system=None, arch=None):
    """Sucht aus den Release-Dateien das Paket für dieses System; None, wenn keins passt."""
    if system is None:
        system, arch = plattform()
    endungen = {"linux": (".tar.gz",), "windows": (".zip",), "macos": (".dmg",)}[system]
    for asset in assets:
        name = asset.get("name", "").lower()
        if f"-{system}-{arch}." in name and name.endswith(endungen):
            return asset
    return None


def _holen(url, wartezeit=WARTEZEIT):
    kopf = {"Accept": "application/vnd.github+json", "User-Agent": "Ueberzeit-Desktop"}
    anfrage = urllib.request.Request(url, headers=kopf)
    try:
        # nosec: feste https-Adresse
        with urllib.request.urlopen(anfrage, timeout=wartezeit, context=ssl_kontext()) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise UpdateFehler(
                "GitHub hat zu viele Anfragen gezählt – später noch einmal versuchen.") from e
        raise UpdateFehler(f"GitHub antwortet mit Fehler {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdateFehler(f"Keine Verbindung zu GitHub: {getattr(e, 'reason', e)}") from e
    except ValueError as e:
        raise UpdateFehler("Unerwartete Antwort von GitHub.") from e


def suchen(aktuell, url=API_URL, system=None, arch=None):
    """Neuere Version auf GitHub? Gibt ein Dict zurück oder None, wenn ``aktuell`` die neueste ist.

    {'version', 'seite', 'notizen', 'paket': {'name', 'url', 'groesse', 'sha256'} oder None}
    'paket' ist None, wenn es für dieses System keins gibt (dann nur Hinweis + Release-Seite)."""
    release = _holen(url)
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease") or not ist_neuer(tag, aktuell):
        return None
    info = {"version": ".".join(map(str, version_tupel(tag))),
            "seite": release.get("html_url") or RELEASE_SEITE,
            "notizen": (release.get("body") or "").strip(), "paket": None}
    asset = paket_waehlen(release.get("assets", []), system, arch)
    if asset:
        digest = asset.get("digest") or ""
        info["paket"] = {"name": asset["name"], "url": asset["browser_download_url"],
                         "groesse": asset.get("size", 0),
                         "sha256": digest[7:].lower() if digest.startswith("sha256:") else ""}
    return info


# --- Herunterladen und auspacken -----------------------------------------------------------

def _sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(BLOCK), b""):
            h.update(block)
    return h.hexdigest()


def herunterladen(paket, ordner, fortschritt=None):
    """Lädt das Paket nach ``ordner`` und prüft die Prüfsumme.

    Liegt es schon fertig da, wird es nicht neu geladen.

    fortschritt(geladen, gesamt) wird zwischendurch aufgerufen."""
    if not re.fullmatch(r"[0-9a-f]{64}", paket.get("sha256", "")):
        raise UpdateFehler("GitHub nennt für das Paket keine Prüfsumme – "
                           "es wird nicht automatisch installiert.")
    if not paket["url"].startswith("https://"):
        raise UpdateFehler("Unsichere Download-Adresse.")
    os.makedirs(ordner, exist_ok=True)
    ziel = os.path.join(ordner, os.path.basename(paket["name"]))
    if os.path.exists(ziel) and _sha256(ziel) == paket["sha256"]:
        return ziel
    teil = ziel + ".part"
    h = hashlib.sha256()
    geladen = 0
    anfrage = urllib.request.Request(paket["url"], headers={"User-Agent": "Ueberzeit-Desktop"})
    try:
        # nosec: feste https-Adresse von GitHub
        with urllib.request.urlopen(anfrage, timeout=60, context=ssl_kontext()) as antwort, \
                open(teil, "wb") as f:
            gesamt = int(antwort.headers.get("Content-Length") or paket.get("groesse") or 0)
            for block in iter(lambda: antwort.read(BLOCK), b""):
                f.write(block)
                h.update(block)
                geladen += len(block)
                if fortschritt:
                    fortschritt(geladen, gesamt)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _weg(teil)
        raise UpdateFehler(f"Download abgebrochen: {getattr(e, 'reason', e)}") from e
    if h.hexdigest() != paket["sha256"]:
        _weg(teil)
        raise UpdateFehler("Die Prüfsumme des Downloads stimmt nicht – Update verworfen.")
    os.replace(teil, ziel)
    return ziel


def _weg(pfad):
    try:
        if os.path.isdir(pfad) and not os.path.islink(pfad):
            shutil.rmtree(pfad)
        elif os.path.lexists(pfad):
            os.remove(pfad)
    except OSError as e:
        logger.warning("Konnte %s nicht entfernen: %s", pfad, e)


def _sicher(ziel, name):
    """Kein Eintrag im Archiv darf aus dem Zielordner herausführen."""
    pfad = os.path.realpath(os.path.join(ziel, name))
    if not pfad.startswith(os.path.realpath(ziel) + os.sep):
        raise UpdateFehler(f"Ungültiger Pfad im Paket: {name}")


def auspacken(archiv, ordner):
    """Packt das Paket nach ``<ordner>/neu`` aus und gibt diesen Ordner zurück.

    Darin liegen danach genau die Programmdateien, die ausgetauscht werden: der Inhalt des
    Programmordners (Linux/Windows) bzw. die .app (macOS)."""
    neu = os.path.join(ordner, NEU)
    roh = os.path.join(ordner, "auspacken")
    _weg(neu)
    _weg(roh)
    os.makedirs(roh)
    try:
        _entpacken(archiv, roh)
        eintraege = [e for e in os.listdir(roh) if not e.startswith(".")]
        if archiv.endswith(".dmg"):
            quelle = roh                               # enthält die .app
            if not any(e.endswith(".app") for e in eintraege):
                raise UpdateFehler("Im Paket fehlt die .app.")
        elif len(eintraege) == 1 and os.path.isdir(os.path.join(roh, eintraege[0])):
            quelle = os.path.join(roh, eintraege[0])   # Ordner „Überzeit-Rechner/“
        else:
            raise UpdateFehler("Das Paket hat einen unerwarteten Aufbau.")
        if not os.path.isdir(os.path.join(quelle, "_internal")) and not archiv.endswith(".dmg"):
            raise UpdateFehler("Im Paket fehlt der Ordner _internal.")
        os.replace(quelle, neu)
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as e:
        _weg(neu)
        raise UpdateFehler(f"Paket konnte nicht ausgepackt werden: {e}") from e
    finally:
        _weg(roh)
    return neu


def _entpacken(archiv, roh):
    """Packt zip/tar.gz/dmg roh nach ``roh`` aus; kein Eintrag darf aus ``roh`` herausführen."""
    if archiv.endswith(".zip"):
        with zipfile.ZipFile(archiv) as z:
            for name in z.namelist():
                _sicher(roh, name)
            z.extractall(roh)
    elif archiv.endswith(".tar.gz"):
        with tarfile.open(archiv, "r:gz") as t:
            for m in t.getmembers():
                _sicher(roh, m.name)
            t.extractall(roh, filter="data")
    elif archiv.endswith(".dmg"):
        _dmg_auspacken(archiv, roh)
    else:
        raise UpdateFehler(f"Unbekanntes Paketformat: {os.path.basename(archiv)}")


def _dmg_auspacken(archiv, ziel):
    mount = os.path.join(os.path.dirname(ziel), "dmg")
    os.makedirs(mount, exist_ok=True)
    subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen",
                    "-mountpoint", mount, archiv], check=True, capture_output=True, timeout=120)
    try:
        for e in os.listdir(mount):
            if e.endswith(".app"):
                subprocess.run(["ditto", os.path.join(mount, e), os.path.join(ziel, e)],
                               check=True, timeout=300)
    finally:
        subprocess.run(["hdiutil", "detach", mount, "-force"],
                       capture_output=True, timeout=60, check=False)
        _weg(mount)


# --- Installieren --------------------------------------------------------------------------

def kann_installieren(base_dir):
    """(True, '') oder (False, Grund) – ob diese App sich selbst austauschen kann.

    base_dir ist config.BASE_DIR: der Programmordner, unter macOS der Ordner mit der .app."""
    if not getattr(sys, "frozen", False):
        return False, "Die App läuft aus dem Quellcode (git pull statt Update)."
    if not os.access(base_dir, os.W_OK):
        return False, "Der Programmordner ist schreibgeschützt."
    return True, ""


def tauschen(neu, ziel, alt):
    """Ersetzt in ``ziel`` jede Datei/jeden Ordner aus ``neu``; die alten wandern nach ``alt``.

    Andere Dateien in ``ziel`` (Datenbank, Einstellungen, Backups, Protokoll) bleiben. Schlägt ein
    Schritt fehl, wird alles Bisherige zurückgetauscht und UpdateFehler geworfen."""
    _weg(alt)
    os.makedirs(alt)
    erledigt = []           # (name, hatte_alt)
    try:
        for name in sorted(os.listdir(neu)):
            hatte_alt = os.path.lexists(os.path.join(ziel, name))
            if hatte_alt:
                os.rename(os.path.join(ziel, name), os.path.join(alt, name))
            erledigt.append((name, hatte_alt))
            os.rename(os.path.join(neu, name), os.path.join(ziel, name))
    except OSError as e:
        for name, hatte_alt in reversed(erledigt):
            try:
                im_ziel, in_neu = os.path.join(ziel, name), os.path.join(neu, name)
                if os.path.lexists(im_ziel) and not os.path.lexists(in_neu):
                    os.rename(im_ziel, in_neu)
                if hatte_alt:
                    os.rename(os.path.join(alt, name), os.path.join(ziel, name))
            except OSError as e2:
                logger.error("Zurücktauschen von %s fehlgeschlagen: %s", name, e2)
        raise UpdateFehler(f"Austausch fehlgeschlagen, alte Version bleibt: {e}") from e


# Windows: laufende .exe/.dll sind gesperrt. Das Skript wartet, bis die App beendet ist, tauscht
# dann wie tauschen() und startet auf Wunsch neu. Nur ASCII im Skript – die Pfade (mit „Ü“) kommen
# als Argumente.
_WINDOWS_SKRIPT = r"""@echo off
setlocal
set "PID=%~1"
set "NEU=%~2"
set "APP=%~3"
set "ALT=%~4"
set "EXE=%~5"
set "START=%~6"
set "LOG=%~7"
set /a N=0
:warte
tasklist /FI "PID eq %PID%" /NH 2>nul | find " %PID% " >nul
if errorlevel 1 goto los
set /a N+=1
if %N% GEQ 120 goto zeit
ping -n 2 127.0.0.1 >nul
goto warte
:zeit
echo App nach 2 Minuten noch nicht beendet - Update abgebrochen>> "%LOG%"
exit /b 1
:los
ping -n 3 127.0.0.1 >nul
if exist "%ALT%" rmdir /s /q "%ALT%"
mkdir "%ALT%" || goto fehler
for /d %%D in ("%NEU%\*") do if exist "%APP%\%%~nxD" move "%APP%\%%~nxD" "%ALT%\" >nul || goto zurueck
for %%F in ("%NEU%\*") do if exist "%APP%\%%~nxF" move /y "%APP%\%%~nxF" "%ALT%\" >nul || goto zurueck
for /d %%D in ("%NEU%\*") do move "%%D" "%APP%\" >nul || goto zurueck
for %%F in ("%NEU%\*") do move /y "%%F" "%APP%\" >nul || goto zurueck
echo Update installiert>> "%LOG%"
if "%START%"=="1" start "" "%APP%\%EXE%"
exit /b 0
:zurueck
echo Austausch fehlgeschlagen - alte Version wird wiederhergestellt>> "%LOG%"
for /d %%D in ("%ALT%\*") do if exist "%APP%\%%~nxD" rmdir /s /q "%APP%\%%~nxD"
for /d %%D in ("%ALT%\*") do move "%%D" "%APP%\" >nul
for %%F in ("%ALT%\*") do move /y "%%F" "%APP%\" >nul
:fehler
echo Update fehlgeschlagen>> "%LOG%"
if "%START%"=="1" start "" "%APP%\%EXE%"
exit /b 1
"""


def installieren(ordner, base_dir, neustart):
    """Tauscht die ausgepackte Version aus ``<ordner>/neu`` ein.

    Aufruf erst, wenn die App gleich endet (Einstellungen gespeichert, Datenbank geschlossen).
    Mit ``neustart`` startet danach die neue Version. Schlägt der Austausch fehl, bleibt die alte
    Version (UpdateFehler bzw. unter Windows ``update.log``)."""
    neu, alt, ziel = os.path.join(ordner, NEU), os.path.join(ordner, ALT), base_dir
    if not os.path.isdir(neu):
        raise UpdateFehler("Kein ausgepacktes Update vorhanden.")
    if sys.platform == "win32":
        skript = os.path.join(ordner, "update.cmd")
        with open(skript, "w", encoding="ascii", newline="\r\n") as f:
            f.write(_WINDOWS_SKRIPT)
        argumente = [str(os.getpid()), neu, ziel, alt, os.path.basename(sys.executable),
                     "1" if neustart else "0", os.path.join(ordner, "update.log")]
        befehl = 'cmd.exe /d /s /c ""' + skript + '" ' + " ".join(f'"{a}"' for a in argumente) + '"'
        # pylint: disable=consider-using-with
        subprocess.Popen(befehl, cwd=ordner, close_fds=True,
                         creationflags=(subprocess.CREATE_NO_WINDOW
                                        | subprocess.CREATE_NEW_PROCESS_GROUP))
        logger.info("Update-Skript gestartet, tauscht nach dem Beenden.")
        return
    tauschen(neu, ziel, alt)
    logger.info("Update installiert.")
    if neustart:
        _neu_starten(ziel)


def _neu_starten(ziel):
    if sys.platform == "darwin":     # sys.executable = <ziel>/X.app/Contents/MacOS/X
        app = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))))
        befehl = ["open", "-n", os.path.join(ziel, app)]
    else:
        befehl = [os.path.join(ziel, os.path.basename(sys.executable))]
    # pylint: disable=consider-using-with
    subprocess.Popen(befehl, cwd=ziel, start_new_session=True, close_fds=True)


def aufraeumen(ordner):
    """Beim Start: Reste eines erledigten Updates löschen (alte Programme, Pakete, Hilfsskript).

    Das Protokoll update.log bleibt zur Fehlersuche."""
    if not os.path.isdir(ordner):
        return
    for name in os.listdir(ordner):
        if name != "update.log":
            _weg(os.path.join(ordner, name))
