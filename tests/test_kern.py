"""
Tests für kern.py — die Rechenregeln ohne Qt, die Desktop-App und Server-Version (web/) teilen.
"""
# pylint: disable=missing-function-docstring
import kern
from models import WorkEntry


SETTINGS = {
    "country": "DE", "state": "TH", "auto_break": True, "max_work_hours": 10,
    "weekday_targets": ["08:00", "08:00", "08:00", "08:00", "06:00", "", ""],
    "break_rules": [{"after": 360, "break": 30}, {"after": 540, "break": 45}],
    "special_days": [{"month": 12, "day": 24, "target": "04:00"}],
}


def work(i, date, start, end, **kw):
    return WorkEntry(i, date, start, end, kw.get("pause", 0), kw.get("minutes", 0), "",
                     kw.get("target", -1), kw.get("typ", kern.TYPE_WORK))


def test_parse_hhmm():
    assert kern.parse_hhmm("07:30") == 450
    assert kern.parse_hhmm("7:30") is None          # wie QTime.fromString(.., "HH:mm")
    assert kern.parse_hhmm("24:00") is None
    assert kern.hhmm_to_minutes("kaputt") == 0
    assert kern.minutes_to_hhmm(25 * 60 + 5) == "01:05"


def test_target_minutes_for_date():
    assert kern.get_target_minutes_for_date("2026-10-12", [], SETTINGS) == 480   # Montag
    assert kern.get_target_minutes_for_date("2026-10-16", [], SETTINGS) == 360   # Freitag 6 h
    assert kern.get_target_minutes_for_date("2026-10-17", [], SETTINGS) == 0     # Samstag
    # Reformationstag (Feiertag in Thüringen)
    assert kern.get_target_minutes_for_date("2026-10-31", [], SETTINGS) == 0
    assert kern.get_target_minutes_for_date("2026-12-24", [], SETTINGS) == 240   # Sondertag
    eigenes = [work(1, "2026-10-12", "08:00", "10:00", target=120)]
    assert kern.get_target_minutes_for_date("2026-10-12", eigenes, SETTINGS) == 120
    assert kern.get_target_minutes_for_date("kein-datum", [], SETTINGS) == 0


def test_recalculate_day_distributes_overtime_to_last_block():
    entries = [work(1, "2026-10-12", "07:00", "12:00"), work(2, "2026-10-12", "12:30", "16:00"),
               WorkEntry(3, "2026-10-12", "", "", 0, -30, "Korrektur", -1, kern.TYPE_WORK)]
    changed = kern.recalculate_day("2026-10-12", entries, SETTINGS)
    assert {e.id for e in changed} == {1, 2}                      # Korrektur bleibt unberührt
    assert [(e.pause, e.minutes) for e in entries] == [(0, 0), (0, 30), (0, -30)]


def test_recalculate_day_absences():
    entries = [WorkEntry(1, "2026-10-16", "", "", 0, 99, "", -1, kern.TYPE_FLEXTIME),
               WorkEntry(2, "2026-10-15", "", "", 0, 99, "", -1, kern.TYPE_SICK)]
    kern.recalculate_day("2026-10-16", entries, SETTINGS)
    kern.recalculate_day("2026-10-15", entries, SETTINGS)
    assert [e.minutes for e in entries] == [-360, 0]


def test_find_overlap_and_midnight():
    entries = [work(1, "2026-10-12", "07:00", "12:00"), work(2, "2026-10-13", "00:00", "02:00")]
    assert kern.find_overlap(entries, "2026-10-12", "11:00", "13:00").id == 1
    assert kern.find_overlap(entries, "2026-10-12", "12:00", "13:00") is None
    # über Mitternacht: der zweite Teil trifft den Eintrag am Folgetag
    assert kern.find_overlap(entries, "2026-10-12", "22:00", "01:00").id == 2
    assert kern.find_overlap(entries, "2026-10-12", "07:00", "12:00", exclude_id=1) is None


def test_consolidate_blocks_bridges_weekend():
    days = ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-21"]
    entries = [WorkEntry(i, d, "", "", 0, 0, "", -1, kern.TYPE_VACATION)
               for i, d in enumerate(days)]
    blocks = kern.consolidate_blocks(entries, entries, SETTINGS)
    assert [[e.date for e in b] for b in blocks] == [["2026-10-21"], days[:3]]
