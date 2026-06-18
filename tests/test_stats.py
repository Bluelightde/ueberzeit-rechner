"""
Unit-Tests für die reinen KPI-Hilfsfunktionen des Statistik-Tabs:
  - _month_span: Kalendermonats-Spanne (Nenner für ⌀ pro Monat)
  - _longest_streaks: längste Plus-/Minus-Serie in aufeinanderfolgenden Tagen
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, protected-access
import pytest

pytest.importorskip("matplotlib")
from tabs.stats_tab import StatsTab  # noqa: E402  pylint: disable=wrong-import-position


# ---------------------------------------------------------------------------
# _month_span – Nenner für den Monatsdurchschnitt
# ---------------------------------------------------------------------------

class TestMonthSpan:

    def test_leer_ist_null(self):
        assert StatsTab._month_span({}) == 0

    def test_ein_monat(self):
        assert StatsTab._month_span({"2024-03": 100}) == 1

    def test_spanne_zaehlt_luecken_mit(self):
        # März und Dezember 2024 → 10 Monate, obwohl nur 2 Monate Daten haben.
        # (Regression: vorher wurde durch die 2 aktiven Monate geteilt.)
        assert StatsTab._month_span({"2024-03": 50, "2024-12": -20}) == 10

    def test_ueber_jahresgrenze(self):
        # November 2023 .. Februar 2024 = 4 Monate
        assert StatsTab._month_span({"2023-11": 10, "2024-02": 5}) == 4


# ---------------------------------------------------------------------------
# _longest_streaks – aufeinanderfolgende Kalendertage
# ---------------------------------------------------------------------------

class TestLongestStreaks:

    def test_leer(self):
        assert StatsTab._longest_streaks({}) == (0, 0)

    def test_aufeinanderfolgende_plus_tage(self):
        daily = {"2024-01-01": 10, "2024-01-02": 5, "2024-01-03": 20}
        plus, minus = StatsTab._longest_streaks(daily)
        assert plus == 3
        assert minus == 0

    def test_luecke_unterbricht_serie(self):
        # Zwei Plus-Tage mit Lücke dazwischen → längste Serie 1, nicht 2.
        # (Regression: vorher wurden nur erfasste Tage gezählt, ohne Adjazenz.)
        daily = {"2024-01-01": 10, "2024-01-10": 5}
        plus, _ = StatsTab._longest_streaks(daily)
        assert plus == 1

    def test_minus_serie(self):
        daily = {"2024-01-01": -5, "2024-01-02": -3, "2024-01-03": 10}
        plus, minus = StatsTab._longest_streaks(daily)
        assert minus == 2
        assert plus == 1

    def test_nulltag_unterbricht_serie(self):
        daily = {"2024-01-01": 10, "2024-01-02": 0, "2024-01-03": 10}
        plus, _ = StatsTab._longest_streaks(daily)
        assert plus == 1
