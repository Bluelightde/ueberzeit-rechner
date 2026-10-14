"""
Tests für abgleich.py — Einträge zwischen Desktop-App und Server-Version in beide Richtungen.

planen() wird für sich geprüft; der Rundweg läuft mit einer echten Desktop-Datenbank (DBManager)
gegen die echte Server-Version (web/) auf einem freien Port, falls Flask installiert ist.
"""
# pylint: disable=missing-function-docstring,import-outside-toplevel,redefined-outer-name
import os
import sys
import threading

import pytest

import abgleich
import kern
from database import DBManager
from models import BereitschaftEntry, WorkEntry


def _s(h, zeit=""):
    return {"hash": h, "geaendert": zeit}


def test_planen_wer_hat_geaendert():
    stand = {"a": "1", "b": "1", "c": "1", "d": "1", "e": "1"}
    lokal = {"a": _s("1"), "b": _s("2"), "c": _s("1"), "d": _s(""), "e": _s("2")}
    server = {"a": _s("1"), "b": _s("1"), "c": _s("3"), "d": _s("1"), "e": _s("2")}
    plan = abgleich.planen(lokal, stand, server)
    assert plan["gleich"] == ["a", "e"]
    assert plan["senden"] == ["b", "d"]      # d: hier gelöscht -> auf dem Server löschen
    assert plan["holen"] == ["c"]
    assert not plan["konflikte"]


def test_planen_erstes_mal_und_konflikte():
    # ohne gemeinsamen Stand: eine Seite leer -> die andere gewinnt (nie etwas löschen)
    plan = abgleich.planen({"a": _s("1")}, {}, {"b": _s("2")})
    assert (plan["senden"], plan["holen"], plan["konflikte"]) == (["a"], ["b"], [])
    # beide geändert -> die neuere Änderung gewinnt, gleich alt -> hier gewinnt
    lokal = {"x": _s("2", "2026-10-14T10:00:00.000Z"), "y": _s("2", "2026-10-14T08:00:00.000Z"),
             "z": _s("2")}
    server = {"x": _s("3", "2026-10-14T09:00:00.000Z"), "y": _s("3", "2026-10-14T09:00:00.000Z"),
              "z": _s("3")}
    plan = abgleich.planen(lokal, {"x": "1", "y": "1", "z": "1"}, server)
    assert plan["senden"] == ["x", "z"] and plan["holen"] == ["y"]
    assert plan["konflikte"] == ["x", "y", "z"]
    # ohne gemeinsamen Stand, beide mit Inhalt -> ebenfalls nach Zeit
    plan = abgleich.planen({"t": _s("2", "2026-10-01T00:00:00Z")}, {},
                           {"t": _s("3", "2026-10-02T00:00:00Z")})
    assert plan["holen"] == ["t"] and plan["konflikte"] == ["t"]


def test_fingerabdruck_ohne_ids_und_reihenfolge():
    a = WorkEntry(1, "2026-10-12", "07:00", "12:00", 0, 0, None, None, "work")
    b = WorkEntry(2, "2026-10-12", "12:30", "16:00", 0, 30, "Test", -1, "work")
    b2 = WorkEntry(99, "2026-10-12", "12:30", "16:00", 0, 30, "Test", -1, "work")
    assert kern.tag_hash(kern.tag_inhalt([a, b])) == kern.tag_hash(kern.tag_inhalt([b2, a]))
    assert kern.tag_hash(kern.tag_inhalt()) == ""
    inhalt = kern.tag_inhalt([a], [BereitschaftEntry(1, "2026-10-12", "18:00", "", None, None)])
    assert kern.tag_inhalt_pruefen(inhalt) == inhalt
    for kaputt in ({"eintraege": [{"start": "7:00"}]}, {"eintraege": [{"type": "urlaub"}]},
                   {"eintraege": [{"minutes": True}]}, {"bereitschaft": [{"end_date": "morgen"}]},
                   {"eintraege": [{}] * 51}, None):
        with pytest.raises(ValueError):
            kern.tag_inhalt_pruefen(kaputt)


def test_desktop_merkt_aenderungen(tmp_path):
    db = DBManager(str(tmp_path / "d.db"))
    e = WorkEntry(None, "2026-10-12", "07:00", "16:00", 30, 30, "", -1, "work")
    db.insert(e)
    assert db.tage_lokal()["2026-10-12"]["geaendert"]
    db.conn.execute("UPDATE tag_geaendert SET zeit = 'alt'")
    db.update(e)                                    # nichts geändert -> Zeit bleibt
    assert db.tage_lokal()["2026-10-12"]["geaendert"] == "alt"
    e.reason = "Anders"
    db.update(e)
    assert db.tage_lokal()["2026-10-12"]["geaendert"] != "alt"
    db.delete(e.id)              # gelöschter Tag bleibt mit leerem Fingerabdruck bekannt
    assert db.tage_lokal()["2026-10-12"]["hash"] == ""
    db.close()


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
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", token, anwendung, speicher
    srv.shutdown()
    sys.path.remove(web)


def _abgleichen(db, adresse, token):
    ergebnis = abgleich.ausfuehren(adresse, token, db.tage_lokal(), db.abgleich_stand())
    return abgleich.uebernehmen(db, ergebnis), ergebnis


def _server_tage(anwendung, speicher):
    with anwendung.app_context():
        return {d: v["inhalt"] for d, v in speicher.tage_inhalt(
            1, speicher.tage_stand(1)).items() if v["hash"]}


def test_rundweg_beide_richtungen(server, tmp_path):
    adresse, token, anwendung, speicher = server
    db = DBManager(str(tmp_path / "desktop.db"))
    db.insert(WorkEntry(None, "2026-10-12", "07:00", "16:00", 30, 30, "Release", -1, "work"))
    db.insert(WorkEntry(None, "2026-10-13", "", "", 0, 0, "", -1, "vacation"))
    db.insert_bereitschaft(
        BereitschaftEntry(None, "2026-10-13", "18:00", "", "Hotline", "2026-10-14"))

    # 1. erster Abgleich: alles zum Server
    geholt, erg = _abgleichen(db, adresse, token)
    assert (geholt, erg["gesendet"]) == (0, 2)
    server_tag = _server_tage(anwendung, speicher)["2026-10-12"]
    assert server_tag == db.tage_lokal()["2026-10-12"]["inhalt"]
    assert _abgleichen(db, adresse, token)[1]["gesendet"] == 0           # nichts mehr zu tun

    # 2. im Browser geändert -> kommt auf den Desktop
    with anwendung.app_context():
        e = next(x for x in speicher.eintraege(1) if x.date == "2026-10-12")
        e.end, e.minutes = "17:00", 90
        speicher.eintrag_aendern(1, e)
        speicher.eintrag_anlegen(
            1, WorkEntry(None, "2026-10-15", "08:00", "12:00", 0, -240, "Web", -1, "work"))
        speicher.db().commit()
    geholt, erg = _abgleichen(db, adresse, token)
    assert (geholt, erg["gesendet"]) == (2, 0)
    tage = {x.date: x for x in db.load_all()}
    assert (tage["2026-10-12"].end, tage["2026-10-12"].minutes) == ("17:00", 90)
    assert tage["2026-10-15"].reason == "Web"

    # 3. am Desktop gelöscht -> auf dem Server gelöscht (Bereitschaft desselben Tages auch)
    db.delete(tage["2026-10-13"].id)
    db.delete_bereitschaft(db.load_all_bereitschaft()[0].id)
    assert _abgleichen(db, adresse, token)[1]["gesendet"] == 1
    assert "2026-10-13" not in _server_tage(anwendung, speicher)

    # 4. Konflikt: derselbe Tag auf beiden Seiten geändert -> die neuere Änderung gewinnt
    e15 = tage["2026-10-15"]
    e15.reason = "Desktop (älter)"
    db.update(e15)
    db.conn.execute("UPDATE tag_geaendert SET zeit = '2020-01-01T00:00:00.000Z' "
                    "WHERE date = '2026-10-15'")
    db.conn.commit()
    with anwendung.app_context():
        w = next(x for x in speicher.eintraege(1) if x.date == "2026-10-15")
        w.reason = "Web (neuer)"
        speicher.eintrag_aendern(1, w)
        speicher.db().commit()
    geholt, erg = _abgleichen(db, adresse, token)
    assert erg["konflikte"] == ["2026-10-15"] and geholt == 1
    assert {x.date: x for x in db.load_all()}["2026-10-15"].reason == "Web (neuer)"

    # 5. Backup wiederhergestellt -> der Desktop-Stand gewinnt und überschreibt den Server
    db.abgleich_neu_beginnen()
    with anwendung.app_context():
        w = next(x for x in speicher.eintraege(1) if x.date == "2026-10-12")
        w.reason = "vor dem Wiederherstellen im Web"
        speicher.eintrag_aendern(1, w)
        speicher.db().commit()
    db.conn.execute("UPDATE tag_geaendert SET zeit = '2099-01-01T00:00:00.000Z'")
    db.conn.commit()
    _abgleichen(db, adresse, token)
    assert _server_tage(anwendung, speicher)["2026-10-12"]["eintraege"][0]["reason"] == "Release"
    assert _abgleichen(db, adresse, token)[1]["gesendet"] == 0
    db.close()


def test_server_lehnt_ab_wenn_inzwischen_geaendert(server):
    adresse, token, anwendung, speicher = server
    inhalt = kern.tag_inhalt(
        [WorkEntry(None, "2026-10-12", "07:00", "08:00", 0, -420, "", -1, "work")])
    tag = {"inhalt": inhalt, "geaendert": "2026-10-14T10:00:00.000Z", "erwartet": "abc"}
    pfad = "/api/geraet/tage/schreiben"
    antwort = abgleich.anfrage(adresse, token, pfad, {"tage": {"2026-10-12": tag}})
    assert antwort["abgelehnt"] == {"2026-10-12": "geändert"} and not antwort["geschrieben"]
    tag["erwartet"] = ""
    kaputt = dict(tag, inhalt={"eintraege": [{"start": "x"}]})
    tage = {"2026-10-12": tag, "kein-datum": tag, "2026-10-13": kaputt}
    antwort = abgleich.anfrage(adresse, token, pfad, {"tage": tage})
    assert list(antwort["geschrieben"]) == ["2026-10-12"]
    assert set(antwort["abgelehnt"]) == {"kein-datum", "2026-10-13"}
    with anwendung.app_context():
        assert speicher.tage_stand(1)["2026-10-12"]["geaendert"] == "2026-10-14T10:00:00.000Z"
    with pytest.raises(abgleich.ServerFehler, match="unbekannt"):
        abgleich.ausfuehren(adresse, "uz_falsch", {}, {})
