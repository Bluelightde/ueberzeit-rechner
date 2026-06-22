"""
Unit-Tests für database.py (DBManager):
  - Tabellenerstellung und Migration
  - insert / load_all / update / delete
  - get_last_entry_before
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, redefined-outer-name
import os
import pytest
import sqlite3
from models import WorkEntry
from database import DBManager, SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-Memory-Datenbank für jeden Test frisch erstellt."""
    manager = DBManager(":memory:")
    yield manager
    manager.close()


# pylint: disable=too-many-arguments, too-many-positional-arguments
def make_entry(entry_id=None, date="2024-06-01", start="08:00", end="17:00",
               pause=30, minutes=510, reason="Test", target_minutes=-1):
    """Erstellt einen WorkEntry. entry_id=None simuliert einen noch nicht gespeicherten Eintrag."""
    return WorkEntry(
        id=entry_id,
        date=date,
        start=start,
        end=end,
        pause=pause,
        minutes=minutes,
        reason=reason,
        target_minutes=target_minutes,
    )


# ---------------------------------------------------------------------------
# Tabellenerstellung
# ---------------------------------------------------------------------------

class TestCreateTable:

    def test_tabelle_wird_erstellt(self, db):
        # load_all würde scheitern, wenn die Tabelle nicht existiert
        entries = db.load_all()
        assert entries == []

    def test_doppeltes_erstellen_ist_idempotent(self, db):
        # create_table nochmal aufrufen darf keinen Fehler werfen
        db.create_table()
        assert db.load_all() == []


# ---------------------------------------------------------------------------
# Insert & Load
# ---------------------------------------------------------------------------

class TestInsertAndLoad:

    def test_insert_weist_id_zu(self, db):
        entry = make_entry()
        assert entry.id is None
        db.insert(entry)
        assert entry.id is not None
        assert entry.id > 0

    def test_insert_und_laden(self, db):
        entry = make_entry(date="2024-06-15", reason="Projektarbeit")
        db.insert(entry)
        loaded = db.load_all()
        assert len(loaded) == 1
        assert loaded[0].date == "2024-06-15"
        assert loaded[0].reason == "Projektarbeit"

    def test_mehrere_eintraege_laden(self, db):
        for i in range(3):
            db.insert(make_entry(date=f"2024-06-{10 + i:02d}"))
        loaded = db.load_all()
        assert len(loaded) == 3

    def test_alle_felder_werden_gespeichert(self, db):
        entry = make_entry(
            date="2024-07-04",
            start="09:15",
            end="18:45",
            pause=45,
            minutes=525,
            reason="Sonderaufgabe",
            target_minutes=480,
        )
        db.insert(entry)
        loaded = db.load_all()[0]
        assert loaded.date == "2024-07-04"
        assert loaded.start == "09:15"
        assert loaded.end == "18:45"
        assert loaded.pause == 45
        assert loaded.minutes == 525
        assert loaded.reason == "Sonderaufgabe"
        assert loaded.target_minutes == 480

    def test_load_all_sortierung_datum_absteigend(self, db):
        db.insert(make_entry(date="2024-06-01"))
        db.insert(make_entry(date="2024-06-03"))
        db.insert(make_entry(date="2024-06-02"))
        loaded = db.load_all()
        dates = [e.date for e in loaded]
        assert dates == sorted(dates, reverse=True)

    def test_load_all_sortierung_startzeit_absteigend(self, db):
        db.insert(make_entry(date="2024-06-01", start="08:00"))
        db.insert(make_entry(date="2024-06-01", start="13:00"))
        loaded = db.load_all()
        assert loaded[0].start == "13:00"
        assert loaded[1].start == "08:00"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdate:

    def test_update_aendert_felder(self, db):
        entry = make_entry(reason="Alt")
        db.insert(entry)
        entry.reason = "Neu"
        entry.pause = 60
        db.update(entry)
        loaded = db.load_all()[0]
        assert loaded.reason == "Neu"
        assert loaded.pause == 60

    def test_update_aendert_nur_den_richtigen_eintrag(self, db):
        e1 = make_entry(date="2024-06-01", reason="Erster")
        e2 = make_entry(date="2024-06-02", reason="Zweiter")
        db.insert(e1)
        db.insert(e2)
        e1.reason = "Geaendert"
        db.update(e1)
        loaded = {e.date: e for e in db.load_all()}
        assert loaded["2024-06-01"].reason == "Geaendert"
        assert loaded["2024-06-02"].reason == "Zweiter"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:

    def test_delete_entfernt_eintrag(self, db):
        entry = make_entry()
        db.insert(entry)
        db.delete(entry.id)
        assert db.load_all() == []

    def test_delete_entfernt_nur_den_richtigen_eintrag(self, db):
        e1 = make_entry(date="2024-06-01")
        e2 = make_entry(date="2024-06-02")
        db.insert(e1)
        db.insert(e2)
        db.delete(e1.id)
        loaded = db.load_all()
        assert len(loaded) == 1
        assert loaded[0].date == "2024-06-02"

    def test_delete_nicht_vorhandene_id_wirft_keinen_fehler(self, db):
        db.delete(99999)  # Darf nicht werfen


# ---------------------------------------------------------------------------
# get_last_entry_before
# ---------------------------------------------------------------------------

class TestGetLastEntryBefore:

    def test_findet_letzten_eintrag(self, db):
        db.insert(make_entry(date="2024-06-01", end="17:00"))
        db.insert(make_entry(date="2024-06-02", end="18:00"))
        result = db.get_last_entry_before("2024-06-05")
        assert result is not None
        assert result.date == "2024-06-02"

    def test_ignoriert_eintraege_ohne_endzeit(self, db):
        db.insert(make_entry(date="2024-06-01", end=""))
        result = db.get_last_entry_before("2024-06-05")
        assert result is None

    def test_gibt_none_zurueck_wenn_nichts_gefunden(self, db):
        db.insert(make_entry(date="2024-06-10", end="17:00"))
        result = db.get_last_entry_before("2024-06-05")
        assert result is None

    def test_datum_selbst_wird_nicht_einbezogen(self, db):
        # Grenzfall: Eintrag am Ziel-Datum selbst darf nicht zurückgegeben werden
        db.insert(make_entry(date="2024-06-05", end="17:00"))
        result = db.get_last_entry_before("2024-06-05")
        assert result is None

    def test_gibt_spaetesten_eintrag_nach_enduhrzeit_zurueck(self, db):
        db.insert(make_entry(date="2024-06-01", end="15:00"))
        db.insert(make_entry(date="2024-06-01", end="17:00"))
        result = db.get_last_entry_before("2024-06-05")
        assert result.end == "17:00"

    def test_rueckgabe_ist_work_entry(self, db):
        db.insert(make_entry(date="2024-06-01", end="17:00"))
        result = db.get_last_entry_before("2024-06-10")
        assert isinstance(result, WorkEntry)


# ---------------------------------------------------------------------------
# insert_many – atomarer Batch-Import (Regression: kein Teilimport)
# ---------------------------------------------------------------------------

class TestInsertMany:

    def test_alle_eintraege_committet_und_ids_gesetzt(self, db):
        entries = [make_entry(date=f"2024-06-{10 + i:02d}") for i in range(3)]
        db.insert_many(entries)
        assert all(e.id is not None for e in entries)
        assert len(db.load_all()) == 3

    def test_fehler_rollt_kompletten_batch_zurueck(self, db):
        # Vorbestand (eigene, committete Transaktion) bleibt erhalten.
        db.insert(make_entry(date="2024-06-01"))
        # Mittlerer Eintrag verletzt NOT NULL (date=None) → IntegrityError.
        bad_batch = [
            make_entry(date="2024-06-10"),
            make_entry(date=None),
            make_entry(date="2024-06-12"),
        ]
        with pytest.raises(sqlite3.Error):
            db.insert_many(bad_batch)
        # Rollback: NICHTS aus dem fehlgeschlagenen Batch bleibt zurück.
        loaded = db.load_all()
        assert len(loaded) == 1
        assert loaded[0].date == "2024-06-01"


# ---------------------------------------------------------------------------
# Schema-Versionierung & Migration (#6)
# ---------------------------------------------------------------------------

class TestSchemaMigration:

    def test_frische_db_hat_aktuelle_version(self, db):
        cur = db.conn.cursor()
        cur.execute("PRAGMA user_version")
        assert cur.fetchone()[0] == SCHEMA_VERSION

    def test_alte_db_wird_migriert(self, tmp_path):
        # "Alte" DB ohne target_minutes / end_date und mit user_version 0.
        path = str(tmp_path / "old.db")
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "date TEXT NOT NULL, start TEXT, end TEXT, pause INTEGER, "
                    "minutes INTEGER, reason TEXT)")
        con.execute("CREATE TABLE bereitschaft_entries (id INTEGER PRIMARY KEY "
                    "AUTOINCREMENT, date TEXT NOT NULL, start TEXT, end TEXT, note TEXT)")
        con.commit()
        con.close()
        mgr = DBManager(path)   # öffnet -> create_table -> Migration
        try:
            cur = mgr.conn.cursor()
            cur.execute("PRAGMA table_info(entries)")
            cols = [r[1] for r in cur.fetchall()]
            assert "target_minutes" in cols
            assert "type" in cols   # v1->v2 Migration (Eintragstypen)
            # v2->v3 Migration (end_time in device_login) — Tabelle existiert
            # nach Migration automatisch; Spalte muss vorhanden sein.
            cur.execute("PRAGMA table_info(device_login)")
            assert "end_time" in [r[1] for r in cur.fetchall()]
            cur.execute("PRAGMA table_info(bereitschaft_entries)")
            assert "end_date" in [r[1] for r in cur.fetchall()]
            cur.execute("PRAGMA user_version")
            assert cur.fetchone()[0] == SCHEMA_VERSION
        finally:
            mgr.close()


# ---------------------------------------------------------------------------
# Device-Login / Logout (Anwesenheits-Übersicht)
# ---------------------------------------------------------------------------

class TestDeviceLoginLogout:

    def test_set_device_login_speichert_erste_zeit(self, db):
        db.set_device_login("2024-06-01", "07:30")
        assert db.get_device_login("2024-06-01") == "07:30"

    def test_set_device_login_ignoriert_bestehenden(self, db):
        db.set_device_login("2024-06-01", "07:30")
        db.set_device_login("2024-06-01", "09:00")  # früherer Login bleibt
        assert db.get_device_login("2024-06-01") == "07:30"

    def test_set_device_logout_aktualisiert_bestehenden(self, db):
        db.set_device_login("2024-06-01", "07:30")
        db.set_device_logout("2024-06-01", "17:00")
        rows = db.load_all_device_logins()
        assert len(rows) == 1
        assert rows[0] == {"date": "2024-06-01", "start": "07:30", "end": "17:00"}

    def test_set_device_logout_legt_eintrag_ohne_login_an(self, db):
        """Logout ohne vorherigen Login → start_time leer, end_time gesetzt."""
        db.set_device_logout("2024-06-02", "18:00")
        rows = db.load_all_device_logins()
        assert rows[0] == {"date": "2024-06-02", "start": "", "end": "18:00"}

    def test_set_device_login_fuellt_leeren_start_nach_logout(self, db):
        """Logout erstellt Zeile mit leerem start_time; späterer Login füllt sie.

        Realistisches Szenario: App schließt kurz nach Mitternacht (Logout
        erstellt Zeile für den neuen Tag mit leerem start), wird später am
        gleichen Tag wieder geöffnet (Login muss start_time nachträglich
        setzen können)."""
        db.set_device_logout("2024-06-02", "00:10")
        db.set_device_login("2024-06-02", "08:00")
        rows = db.load_all_device_logins()
        assert rows[0]["start"] == "08:00"
        assert rows[0]["end"] == "00:10"  # Logout bleibt erhalten

    def test_set_device_logout_ueberschreibt_bestehende_end_time(self, db):
        db.set_device_login("2024-06-01", "07:30")
        db.set_device_logout("2024-06-01", "16:00")
        db.set_device_logout("2024-06-01", "18:30")
        rows = db.load_all_device_logins()
        assert rows[0]["end"] == "18:30"
        assert rows[0]["start"] == "07:30"  # start unverändert

    def test_load_all_device_logins_sortiert_absteigend(self, db):
        db.set_device_login("2024-06-01", "07:30")
        db.set_device_login("2024-06-03", "08:00")
        db.set_device_login("2024-06-02", "07:45")
        rows = db.load_all_device_logins()
        dates = [r["date"] for r in rows]
        assert dates == ["2024-06-03", "2024-06-02", "2024-06-01"]

    def test_get_device_login_none_wenn_nicht_vorhanden(self, db):
        assert db.get_device_login("1999-01-01") is None

    def test_migriert_v2_db_bekommt_end_time_spalte(self, tmp_path):
        """Eine DB mit user_version 2 (device_login ohne end_time) wird
        korrekt auf v3 migriert."""
        path = str(tmp_path / "v2.db")
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "date TEXT NOT NULL, start TEXT, end TEXT, pause INTEGER, "
                    "minutes INTEGER, reason TEXT, target_minutes INTEGER DEFAULT -1, "
                    "type TEXT NOT NULL DEFAULT 'work')")
        con.execute("CREATE TABLE bereitschaft_entries (id INTEGER PRIMARY KEY "
                    "AUTOINCREMENT, date TEXT NOT NULL, start TEXT, end TEXT, "
                    "note TEXT, end_date TEXT)")
        con.execute("CREATE TABLE device_login (date TEXT PRIMARY KEY, "
                    "start_time TEXT NOT NULL)")
        con.execute("PRAGMA user_version = 2")
        con.execute("INSERT INTO device_login (date, start_time) VALUES ('2024-06-01', '07:30')")
        con.commit()
        con.close()
        mgr = DBManager(path)
        try:
            cur = mgr.conn.cursor()
            cur.execute("PRAGMA table_info(device_login)")
            assert "end_time" in [r[1] for r in cur.fetchall()]
            cur.execute("PRAGMA user_version")
            assert cur.fetchone()[0] == SCHEMA_VERSION
            # Bestehende Daten bleiben erhalten
            rows = mgr.load_all_device_logins()
            assert rows[0]["start"] == "07:30"
            assert rows[0]["end"] == ""
        finally:
            mgr.close()

# ---------------------------------------------------------------------------
# Backup / Wiederherstellung (#5)
# ---------------------------------------------------------------------------

class TestBackupRestore:

    def test_backup_und_restore_roundtrip(self, tmp_path):
        mgr = DBManager(str(tmp_path / "data.db"))
        try:
            mgr.insert(make_entry(date="2024-06-01"))
            backup_path = mgr.create_backup(str(tmp_path / "backups"))
            assert os.path.exists(backup_path)
            # Daten NACH dem Backup ändern
            mgr.insert(make_entry(date="2024-06-02"))
            assert len(mgr.load_all()) == 2
            # Wiederherstellen -> Stand des Backups (nur erster Eintrag)
            mgr.restore_from(backup_path)
            loaded = mgr.load_all()
            assert len(loaded) == 1
            assert loaded[0].date == "2024-06-01"
        finally:
            mgr.close()

    def test_prune_behaelt_nur_neueste(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        for day in range(1, 16):   # 15 Backups (Tag 01..15)
            (backup_dir / f"ueberstunden-202401{day:02d}-120000.db").write_text("x")
        DBManager._prune_backups(str(backup_dir), keep=10)
        remaining = sorted(p.name for p in backup_dir.glob("ueberstunden-*.db"))
        assert len(remaining) == 10
        assert remaining[0] == "ueberstunden-20240106-120000.db"  # Tag 01-05 entfernt
