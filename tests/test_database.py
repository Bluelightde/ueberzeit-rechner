"""
Unit-Tests für database.py (DBManager):
  - Tabellenerstellung und Migration
  - insert / load_all / update / delete
  - get_last_entry_before
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, redefined-outer-name
import pytest
from models import WorkEntry
from database import DBManager


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
