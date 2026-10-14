"""
Tests für server_sync.py — die Desktop-App meldet die Anwesenheit an die Server-Version.

Der Rundweg läuft gegen die echte Server-Version (web/) auf einem freien Port, falls Flask
installiert ist.
"""
# pylint: disable=missing-function-docstring,import-outside-toplevel
import os
import sys
import threading

import pytest

import server_sync


def test_tage_auswaehlen():
    zeilen = [{"date": "2026-10-12", "start": "07:12", "end": "16:03"},
              {"date": "2026-10-11", "start": "", "end": ""},          # leer: nicht melden
              {"date": "2026-10-10", "start": "", "end": "15:00"}]
    tage = server_sync.tage_auswaehlen(zeilen, "2026-10-13", "06:55")
    assert tage == [{"date": "2026-10-13", "login": "06:55", "logout": ""},
                    {"date": "2026-10-12", "login": "07:12", "logout": "16:03"},
                    {"date": "2026-10-10", "login": "", "logout": "15:00"}]
    # heute schon mit Logout, aber ohne Login: Login ergänzen
    tage = server_sync.tage_auswaehlen([{"date": "2026-10-13", "start": "", "end": "09:00"}],
                                       "2026-10-13", "08:00")
    assert tage == [{"date": "2026-10-13", "login": "08:00", "logout": "09:00"}]
    viele = [{"date": f"2026-01-{i:02d}", "start": "07:00", "end": ""} for i in range(1, 32)]
    assert len(server_sync.tage_auswaehlen(viele, "2026-10-13", tage=10)) == 10


def test_falsche_angaben():
    with pytest.raises(server_sync.ServerFehler, match="http"):
        server_sync.verbindung_testen("ueberzeit.lan", "uz_x")
    with pytest.raises(server_sync.ServerFehler, match="Gerätezugang"):
        server_sync.verbindung_testen("http://127.0.0.1:9", "")
    with pytest.raises(server_sync.ServerFehler, match="nicht erreichbar"):
        server_sync.verbindung_testen("http://127.0.0.1:9", "uz_x")      # Port 9: niemand da


@pytest.fixture
def server(tmp_path):
    pytest.importorskip("flask")
    from werkzeug.serving import make_server
    web = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    sys.path.insert(0, web)
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("ERSTES_PASSWORT", "geheim123")
    import app as uz
    import speicher
    anwendung = uz.erstelle_app({"DATENBANK": str(tmp_path / "s.db"), "TESTING": True})
    with anwendung.app_context():
        token = speicher.geraet_anlegen(1, "Test-PC")
        speicher.db().commit()
    srv = make_server("127.0.0.1", 0, anwendung)
    faden = threading.Thread(target=srv.serve_forever, daemon=True)
    faden.start()
    yield f"http://127.0.0.1:{srv.server_port}", token, anwendung, speicher
    srv.shutdown()
    sys.path.remove(web)


def test_rundweg_mit_server_version(server):
    adresse, token, anwendung, speicher = server
    assert "Test-PC" in server_sync.verbindung_testen(adresse + "/", token)
    tage = server_sync.tage_auswaehlen([{"date": "2026-10-12", "start": "07:12", "end": "16:03"}],
                                       "2026-10-13", "06:55")
    assert server_sync.anwesenheit_senden(adresse, token, tage) == 2
    with anwendung.app_context():
        assert speicher.anwesenheit_tag(1, "2026-10-12") == {
            "date": "2026-10-12", "start": "07:12", "end": "16:03"}
        assert speicher.anwesenheit_tag(1, "2026-10-13")["start"] == "06:55"
    with pytest.raises(server_sync.ServerFehler, match="unbekannt"):
        server_sync.anwesenheit_senden(adresse, "uz_falsch", tage)
    with pytest.raises(server_sync.ServerFehler, match="keine passende"):
        server_sync.verbindung_testen(adresse + "/gibtsnicht", token)
