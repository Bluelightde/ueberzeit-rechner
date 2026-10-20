"""Autostart und Hintergrundbetrieb (hintergrund.py, Schließen ins Taskleisten-Symbol, main.py)."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access
# pylint: disable=too-many-instance-attributes,attribute-defined-outside-init
import os
import plistlib
import sys
import types

import pytest

import hintergrund


def test_startbefehl_im_skriptbetrieb_mit_main_py():
    befehl = hintergrund.startbefehl()
    assert befehl[0] == sys.executable
    assert befehl[1].endswith("main.py") and os.path.isabs(befehl[1])
    assert befehl[-1] == hintergrund.HINTERGRUND_ARG


def test_startbefehl_im_paket(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/Überzeit-Rechner/Überzeit-Rechner")
    assert hintergrund.startbefehl() == ["/opt/Überzeit-Rechner/Überzeit-Rechner", "--hintergrund"]


def test_linux_autostart_datei(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/home/m/Über zeit/Überzeit-Rechner")
    assert not hintergrund.autostart_aktiv("linux")
    hintergrund.autostart_setzen(True, "linux", icon="/home/m/icon.png")
    datei = tmp_path / "autostart" / "ueberzeit-rechner.desktop"
    text = datei.read_text(encoding="utf-8")
    # Leerzeichen im Pfad werden gequotet
    assert "Exec='/home/m/Über zeit/Überzeit-Rechner' --hintergrund\n" in text
    assert "Icon=/home/m/icon.png" in text and text.startswith("[Desktop Entry]\n")
    assert hintergrund.autostart_aktiv("linux")
    hintergrund.autostart_setzen(False, "linux")
    assert not datei.exists() and not hintergrund.autostart_aktiv("linux")
    hintergrund.autostart_setzen(False, "linux")              # schon aus: kein Fehler


def test_mac_launch_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    programm = "/Applications/Überzeit.app/Contents/MacOS/Überzeit-Rechner"
    monkeypatch.setattr(sys, "executable", programm)
    hintergrund.autostart_setzen(True, "darwin")
    datei = tmp_path / "Library" / "LaunchAgents" / "de.bluelight.ueberzeit-rechner.plist"
    with open(datei, "rb") as f:
        p = plistlib.load(f)
    assert p["ProgramArguments"] == [programm, "--hintergrund"]
    assert p["RunAtLoad"] is True and p["Label"] == "de.bluelight.ueberzeit-rechner"
    assert hintergrund.autostart_aktiv("darwin")
    hintergrund.autostart_setzen(False, "darwin")
    assert not datei.exists()


def test_windows_registry(monkeypatch):
    werte = {}

    class Schluessel:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def query(_s, name):
        if name not in werte:
            raise FileNotFoundError(name)
        return werte[name], 1

    def delete(_s, name):
        if name not in werte:
            raise FileNotFoundError(name)
        del werte[name]

    winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=1,
        OpenKey=lambda *a: Schluessel(), QueryValueEx=query, DeleteValue=delete,
        SetValueEx=lambda _s, name, _r, _t, wert: werte.__setitem__(name, wert))
    monkeypatch.setitem(sys.modules, "winreg", winreg)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Überzeit\Überzeit-Rechner.exe")
    assert not hintergrund.autostart_aktiv("win32")
    hintergrund.autostart_setzen(True, "win32")
    soll = r'"C:\Program Files\Überzeit\Überzeit-Rechner.exe" --hintergrund'
    assert werte["UeberzeitRechner"] == soll
    assert hintergrund.autostart_aktiv("win32")
    hintergrund.autostart_setzen(False, "win32")
    assert not werte and not hintergrund.autostart_aktiv("win32")
    hintergrund.autostart_setzen(False, "win32")


def test_instanz_name_je_ordner(tmp_path):
    a = hintergrund.instanz_name(str(tmp_path / "a"))
    assert a == hintergrund.instanz_name(str(tmp_path / "a"))
    assert a != hintergrund.instanz_name(str(tmp_path / "b"))


# --- Schließen: ins Symbol statt beenden ---

class _Ereignis:
    def __init__(self):
        self.ignoriert = False

    def ignore(self):
        self.ignoriert = True


class _Fenster:
    """Nur das, was closeEvent/_aufraeumen anfassen."""
    def __init__(self, hintergrund_an):
        self.settings = {}
        self._an = hintergrund_an
        self._wirklich_beenden = False
        self._aufgeraeumt = False
        self._update_bereit = False
        self.versteckt = self.gespeichert = self.db_zu = 0
        self.meldungen = []
        self._tray = types.SimpleNamespace(showMessage=lambda *a: self.meldungen.append(a),
                                           hide=lambda: None)
        self.db = types.SimpleNamespace(close=self._db_zu)

    def _db_zu(self):
        self.db_zu += 1

    def _hintergrund_an(self):
        return self._an

    def hide(self):
        self.versteckt += 1

    def save_settings(self):
        self.gespeichert += 1


@pytest.fixture
def app_klasse():
    pytest.importorskip("PyQt6")
    import main  # pylint: disable=import-outside-toplevel
    return main.UeberstundenApp


def test_schliessen_versteckt_nur_und_meldet_einmal(app_klasse, monkeypatch):
    monkeypatch.setattr(app_klasse.__mro__[1], "closeEvent", lambda *a: None)
    f = _Fenster(True)
    f._aufraeumen = types.MethodType(app_klasse._aufraeumen, f)
    e = _Ereignis()
    app_klasse.closeEvent(f, e)
    assert e.ignoriert and f.versteckt == 1 and f.db_zu == 0
    assert len(f.meldungen) == 1 and f.settings["tray_hinweis_gezeigt"] is True
    app_klasse.closeEvent(f, _Ereignis())
    assert len(f.meldungen) == 1                       # der Hinweis kommt nur beim ersten Mal


def test_ohne_symbol_oder_beenden_wird_aufgeraeumt(app_klasse, monkeypatch):
    monkeypatch.setattr(app_klasse.__mro__[1], "closeEvent", lambda *a: None)
    f = _Fenster(False)
    f._aufraeumen = types.MethodType(app_klasse._aufraeumen, f)
    e = _Ereignis()
    app_klasse.closeEvent(f, e)
    assert not e.ignoriert and f.db_zu == 1
    app_klasse._aufraeumen(f)                          # aboutToQuit danach: nicht noch einmal
    assert f.db_zu == 1
    g = _Fenster(True)
    g._aufraeumen = types.MethodType(app_klasse._aufraeumen, g)
    g._wirklich_beenden = True                          # Menü „Beenden“
    app_klasse.closeEvent(g, _Ereignis())
    assert g.db_zu == 1 and g.versteckt == 0
