"""Test für das lazy StatsTab-Lifecycle-Verhalten.

Testet die drei Zustände des Guards `if self.tab_stats is not None`:
  1. _on_data_changed ohne StatsTab → puffert Entries
  2. _ensure_stats_tab → baut StatsTab, lädt gepufferte Daten
  3. _on_data_changed mit StatsTab → StatsTab bekommt Update

Keine volle App-Instanz — nur der Lifecycle der drei Zustände.
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, protected-access
import os
import sys

import pytest

pytest.importorskip("PyQt6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication  # noqa: E402  pylint: disable=wrong-import-position

_app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
i18n.setup_i18n("de")

pytest.importorskip("matplotlib")
from tabs.stats_tab import StatsTab  # noqa: E402  pylint: disable=wrong-import-position
from database import DBManager  # noqa: E402
from models import WorkEntry  # noqa: E402
from logic import TYPE_WORK  # noqa: E402

SETTINGS = {"default_start": "07:00", "target_work_time": "08:00"}


def _make_entry(day, minutes=480):
    return WorkEntry(
        id=0, date=f"2026-01-{day:02d}", start="07:00", end="16:00",
        pause=30, minutes=minutes, reason="", target_minutes=-1,
        entry_type=TYPE_WORK,
    )


class TestLazyStatsLifecycle:
    """Testet die drei Guard-Zustände des lazy StatsTab."""

    def test_data_changed_without_stats_tab_pends(self):
        """Zustand 1: tab_stats is None → Entries werden gepuffert."""
        db = DBManager(":memory:")
        db.insert(_make_entry(1))
        entries = db.load_all()

        tab_stats = None
        pending = None
        # Simuliert _on_data_changed ohne StatsTab
        if tab_stats is not None:
            tab_stats.refresh(entries)
        pending = entries

        assert tab_stats is None
        assert len(pending) == 1

    def test_ensure_stats_tab_loads_pended_data(self):
        """Zustand 2: Lazy Init → StatsTab bekommt gepufferte Entries."""
        db = DBManager(":memory:")
        db.insert(_make_entry(1))
        db.insert(_make_entry(2))
        entries = db.load_all()

        # Zustand 1: puffern
        tab_stats = None
        pending = entries

        # Zustand 2: Lazy Init (simuliert _ensure_stats_tab)
        tab_stats = StatsTab(settings=SETTINGS)
        if pending is not None:
            tab_stats.refresh(pending)

        assert len(tab_stats.entries) == 2

    def test_data_changed_with_stats_tab_refreshes(self):
        """Zustand 3: tab_stats ist nicht None → StatsTab wird aktualisiert."""
        db = DBManager(":memory:")
        db.insert(_make_entry(1))
        entries = db.load_all()

        # Zustand 1+2: puffern, dann StatsTab bauen
        tab_stats = StatsTab(settings=SETTINGS)
        tab_stats.refresh(entries)

        # Zustand 3: neue Daten, _on_data_changed mit StatsTab
        db.insert(_make_entry(2))
        entries2 = db.load_all()
        if tab_stats is not None:
            tab_stats.refresh(entries2)

        assert len(tab_stats.entries) == 2

    def test_full_lifecycle_sequence(self):
        """Komplette Sequenz: Daten → Tab öffnen → Daten ändern → Tab aktualisiert."""
        db = DBManager(":memory:")
        for day in range(1, 6):
            db.insert(_make_entry(day))
        entries = db.load_all()

        # 1. _on_data_changed (Konstruktor): StatsTab existiert nicht
        tab_stats = None
        pending = None
        if tab_stats is not None:
            tab_stats.refresh(entries)
        pending = entries
        assert tab_stats is None
        assert len(pending) == 5

        # 2. _ensure_stats_tab: StatsTab wird gebaut mit gepufferten Daten
        tab_stats = StatsTab(settings=SETTINGS)
        if pending is not None:
            tab_stats.refresh(pending)
        assert len(tab_stats.entries) == 5

        # 3. Neue Daten hinzufügen
        db.insert(_make_entry(10))

        # 4. _on_data_changed erneut: Guard greift, StatsTab wird aktualisiert
        entries2 = db.load_all()
        if tab_stats is not None:
            tab_stats.refresh(entries2)
        pending = entries2

        assert len(tab_stats.entries) == 6
        assert len(pending) == 6