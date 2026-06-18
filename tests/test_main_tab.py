"""
Headless-Integrationstest für den Haupt-Tab – Einträge hinzufügen, bearbeiten,
Typ-Wechsel, Recalculate.  Fängt Regressionen wie das date_str/start_str-Definier-
Problem in add_entry ab.
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, protected-access
import os
import sys
import pytest

pytest.importorskip("PyQt6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication  # noqa: E402  pylint: disable=wrong-import-position
from PyQt6.QtCore import QDate, QTime      # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)

import i18n                                      # noqa: E402
i18n.setup_i18n("de")

from database import DBManager                   # noqa: E402
from tabs.main_tab import MainTab                # noqa: E402
from tabs.calendar_tab import CalendarTab        # noqa: E402
from models import WorkEntry                      # noqa: E402
from logic import (                              # noqa: E402
    TYPE_WORK, TYPE_VACATION, TYPE_FLEXTIME, TYPE_PARENTAL,
    ABSENCE_TYPES, get_absence_minutes,
)


SETTINGS = {
    "default_start": "07:00",
    "target_work_time": "08:00",
    "language": "de",
    "country": "DE",
    "state": "TH",
    "auto_break": True,
    "use_login_time": False,
    "max_work_hours": 10,
    "workdays": [0, 1, 2, 3, 4],
    "weekday_targets": ["08:00", "08:00", "08:00", "08:00", "08:00", "", ""],
    "break_rules": [{"after": 360, "break": 30}, {"after": 540, "break": 45}],
    "special_days": [],
    "dark_mode": False,
    "theme": "light",
    "vacation_entitlement": 30,
    "bereitschaft_color": "#eab308",
    "type_colors": {"vacation": "#06b6d4", "sick": "#f97316",
                    "holiday": "#a855f7", "flextime": "#84cc16"},
}


class TestAddEntry:
    """Integration: Widgets füllen → add_entry() → Eintrag in DB & Liste."""

    @pytest.fixture
    def tab(self):
        db = DBManager(":memory:")
        tab = MainTab(db, SETTINGS, lambda: None, lambda: None)
        # Sicherstellen, dass die callbacks __init__ überleben und niemals None sind
        yield tab
        db.close()

    def _drive_entry(self, tab, date_str, start, end, reason="", etype=TYPE_WORK,
                     pause_spin=None, custom_target_cb=None):
        """Hilfsfunktion: Widgets befüllen und add_entry auslösen."""
        y, m, d = map(int, date_str.split("-"))
        tab.date_edit.setDate(QDate(y, m, d))
        # Typ setzen VOR add_entry (sonst greift _on_type_changed ins Leere)
        _idx = tab.type_combo.findData(etype)
        if _idx >= 0:
            tab.type_combo.setCurrentIndex(_idx)
        if etype in ABSENCE_TYPES or etype == TYPE_FLEXTIME:
            # Zeiten sind deaktiviert und irrelevant; trotzdem Werte setzen damit
            # add_entry.start_str/end_str keine Exceptions werfen
            pass
        tab.time_start.setTime(QTime.fromString(start, "HH:mm"))
        tab.time_end.setTime(QTime.fromString(end, "HH:mm"))
        tab.reason_edit.setText(reason)
        tab.update_live_calc()  # setzt current_calculated_pause/overtime
        tab._last_added_params = None
        tab.add_entry()

    def test_arbeitseintrag_wird_gespeichert(self, tab):
        self._drive_entry(tab, "2024-06-03", "08:00", "17:00", "Regulär")
        rows = tab.db.load_all()
        assert len(rows) == 1
        e = rows[0]
        assert e.date == "2024-06-03"
        assert e.start == "08:00"
        assert e.end == "17:00"
        assert e.entry_type == TYPE_WORK

    def test_urlaubs_eintrag_hat_leere_zeiten(self, tab):
        self._drive_entry(tab, "2024-06-04", "08:00", "17:00", "Urlaub", etype=TYPE_VACATION)
        rows = tab.db.load_all()
        assert len(rows) == 1
        e = rows[0]
        assert e.entry_type == TYPE_VACATION
        assert e.start == "" and e.end == ""
        assert e.pause == 0
        # recalculate_day setzt minutes=0 (Saldo-neutral)
        assert e.minutes == 0

    def test_gleitzeitabbau_zieht_soll_ab(self, tab):
        self._drive_entry(tab, "2024-06-05", "08:00", "17:00", "Gleitzeit", etype=TYPE_FLEXTIME)
        rows = tab.db.load_all()
        assert len(rows) == 1
        e = rows[0]
        assert e.entry_type == TYPE_FLEXTIME
        assert e.minutes == -480  # 8h Soll vom Überstunden-Saldo abgezogen

    def test_zwei_eintraege_am_selben_tag(self, tab):
        self._drive_entry(tab, "2024-06-06", "08:00", "12:00", "Vormittag")
        self._drive_entry(tab, "2024-06-06", "13:00", "17:00", "Nachmittag")
        rows = tab.db.load_all()
        assert len(rows) == 2
        for e in rows:
            assert e.date == "2024-06-06"

    def test_nach_add_entry_sind_felder_zurueckgesetzt(self, tab):
        self._drive_entry(tab, "2024-06-07", "08:00", "16:00", "Nach add_entry")
        assert tab.reason_edit.text() == ""
    def test_typ_farben_in_settings(self, tab):
        tc = tab.settings.get("type_colors", {})
        assert tc.get("vacation") == "#06b6d4"
        assert tc.get("sick") == "#f97316"
        assert tc.get("holiday") == "#a855f7"
        assert tc.get("flextime") == "#84cc16"


    def test_absenz_speichert_niemals_zeiten(self, tab):
        for etype in ("vacation", "sick", "holiday"):
            self._drive_entry(tab, "2024-06-10", "08:00", "17:00",
                              f"Test {etype}", etype=etype)
            e = tab.db.load_all()[-1]
            assert e.start == "" and e.end == "", f"{etype}: start/end sollten leer sein"
            assert e.pause == 0, f"{etype}: pause sollte 0 sein"

    def test_recalculate_day_berechnet_timed_neu(self, tab):
        # Eintrag mit absichtlich falschen minutes -> recalculate_day korrigiert
        tab.db.insert(WorkEntry(id=None, date="2024-06-06", start="08:00", end="17:00",
                                pause=0, minutes=99999, reason="x", entry_type="work"))
        tab.entries = tab.db.load_all()
        tab.recalculate_day("2024-06-06")
        e = [x for x in tab.db.load_all() if x.date == "2024-06-06"][0]
        # 9h brutto -> 30min Pflichtpause -> 510 netto - 480 Soll = +30
        assert e.minutes == 30, f"recalculate_day hat nicht neu gerechnet: {e.minutes}"
        assert e.pause == 30

    def test_urlaub_datumsbereich_erzeugt_eintrag_pro_werktag(self, tab):
        # Mo 2024-06-03 bis So 2024-06-09 = 5 Werktage; Wochenende übersprungen
        tab.date_edit.setDate(QDate(2024, 6, 3))
        tab.type_combo.setCurrentIndex(tab.type_combo.findData(TYPE_VACATION))
        tab.date_end_edit.setDate(QDate(2024, 6, 9))
        tab.add_entry()
        vac = [e for e in tab.db.load_all() if e.entry_type == TYPE_VACATION]
        assert len(vac) == 5, f"erwartet 5 Werktage, bekam {len(vac)}"
        assert all(e.start == "" and e.minutes == 0 for e in vac)

    def test_elternzeit_ist_absenz(self, tab):
        assert TYPE_PARENTAL in ABSENCE_TYPES
        tab.date_edit.setDate(QDate(2024, 6, 12))
        tab.type_combo.setCurrentIndex(tab.type_combo.findData(TYPE_PARENTAL))
        tab.add_entry()
        e = [x for x in tab.db.load_all() if x.entry_type == TYPE_PARENTAL][0]
        assert e.minutes == 0 and e.start == "" and e.end == ""

    def test_mehrtaegiger_urlaub_wird_zu_einer_zeile(self, tab):
        # Mo 03.06 bis Fr 07.06 = 5 Werktage -> 5 DB-Einträge, aber 1 Listenzeile
        tab.date_edit.setDate(QDate(2024, 6, 3))
        tab.type_combo.setCurrentIndex(tab.type_combo.findData(TYPE_VACATION))
        tab.date_end_edit.setDate(QDate(2024, 6, 7))
        tab.add_entry()
        tab.update_ui()
        assert len([e for e in tab.db.load_all() if e.entry_type == TYPE_VACATION]) == 5
        assert tab.table.rowCount() == 1
        assert len(tab._display_blocks) == 1 and len(tab._display_blocks[0]) == 5

    def test_feiertag_nicht_mehr_waehlbar(self, tab):
        datas = [tab.type_combo.itemData(i) for i in range(tab.type_combo.count())]
        assert "holiday" not in datas
        assert datas == ["work", "vacation", "sick", "flextime", "parental"]

    def test_mehrtages_abwesenheit_bearbeitbar(self, tab):
        # Block bearbeiten: Urlaub Mo-Fr (5) -> Krank Mo-Mi (3), alte ersetzt
        from dialogs import AbsenceEditDialog
        import unittest.mock as mock
        tab.date_edit.setDate(QDate(2024, 6, 3))
        tab.type_combo.setCurrentIndex(tab.type_combo.findData(TYPE_VACATION))
        tab.date_end_edit.setDate(QDate(2024, 6, 7))
        tab.add_entry()
        tab.update_ui()
        block = tab._display_blocks[0]
        from logic import TYPE_SICK
        dlg = AbsenceEditDialog(block, tab.settings, tab)
        dlg.type_combo.setCurrentIndex(dlg.type_combo.findData(TYPE_SICK))
        dlg.start_edit.setDate(QDate(2024, 6, 3))
        dlg.end_edit.setDate(QDate(2024, 6, 5))
        with mock.patch.object(AbsenceEditDialog, "exec", return_value=1), \
                mock.patch("tabs.main_tab.AbsenceEditDialog", return_value=dlg):
            tab._open_absence_block_dialog(block)
        rows = tab.db.load_all()
        assert [e for e in rows if e.entry_type == TYPE_VACATION] == []
        sick = sorted(e.date for e in rows if e.entry_type == TYPE_SICK)
        assert sick == ["2024-06-03", "2024-06-04", "2024-06-05"]


class TestCalendarRendering:
    """Regression: der Kalender MUSS Zellen tatsächlich in die Tabelle einfügen."""

    def _entries(self):
        return [
            WorkEntry(id=1, date="2024-06-03", start="08:00", end="17:00",
                      pause=30, minutes=30, reason="", entry_type="work"),
            WorkEntry(id=2, date="2024-06-04", start="", end="",
                      pause=0, minutes=0, reason="", entry_type="vacation"),
        ]

    def test_kalender_zellen_werden_gefuellt(self):
        cal = CalendarTab(settings=SETTINGS)
        cal.refresh(self._entries(), [])
        idx = cal.cal_month_filter.findData("2024-06")
        assert idx >= 0, "Monat 2024-06 fehlt im Filter"
        cal.cal_month_filter.setCurrentIndex(idx)
        cal._update_heatmap()
        filled = sum(
            1 for r in range(cal.cal_table.rowCount())
            for c in range(7) if cal.cal_table.item(r, c) is not None
        )
        assert filled > 0, "Kalender-Zellen sind leer (setItem fehlt!)"

    def test_kalender_zeigt_tageszahl(self):
        cal = CalendarTab(settings=SETTINGS)
        cal.refresh(self._entries(), [])
        idx = cal.cal_month_filter.findData("2024-06")
        cal.cal_month_filter.setCurrentIndex(idx)
        cal._update_heatmap()
        texts = [
            cal.cal_table.item(r, c).text()
            for r in range(cal.cal_table.rowCount())
            for c in range(7) if cal.cal_table.item(r, c) is not None
        ]
        # Mindestens ein Tag mit der Zahl "3" (3. Juni)
        assert any("3" in t for t in texts)
