"""
Unit-Tests für logic.py:
  - get_holidays()        : Feiertags-Berechnung für alle 16 Bundesländer
  - calculate_timed_entries() : Pause und Überstunden-Berechnung
"""
# pylint: disable=missing-function-docstring
from PyQt6.QtCore import QDate
from models import WorkEntry
from logic import (
    get_holidays, calculate_timed_entries, is_midnight_shift, split_midnight_shift,
    get_target_minutes_for_date, get_absence_minutes,
    TYPE_WORK, TYPE_VACATION, TYPE_SICK, TYPE_HOLIDAY, TYPE_FLEXTIME,
    ABSENCE_TYPES,
)


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def make_entry(entry_id, start, end, pause=0):
    """Erstellt einen minimalen WorkEntry für Tests."""
    return WorkEntry(
        id=entry_id,
        date="2024-01-15",
        start=start,
        end=end,
        pause=pause,
        minutes=0,
        reason="",
        target_minutes=-1,
    )


# ---------------------------------------------------------------------------
# get_holidays – bundesweite Feiertage
# ---------------------------------------------------------------------------

class TestGetHolidaysBundesweit:
    """Feiertage die in allen Bundesländern gelten."""

    def test_neujahr(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-01-01" in holidays
        assert holidays["2024-01-01"] == "Neujahr"

    def test_tag_der_arbeit(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-05-01" in holidays

    def test_tag_der_deutschen_einheit(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-10-03" in holidays

    def test_erster_weihnachtstag(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-12-25" in holidays

    def test_zweiter_weihnachtstag(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-12-26" in holidays

    def test_karfreitag_2024(self):
        # Ostern 2024: 31. März → Karfreitag: 29. März
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-03-29" in holidays

    def test_ostermontag_2024(self):
        # Ostern 2024: 31. März → Ostermontag: 1. April
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-04-01" in holidays

    def test_christi_himmelfahrt_2024(self):
        # Ostersonntag 31.03. + 39 Tage = 9. Mai
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-05-09" in holidays

    def test_pfingstmontag_2024(self):
        # Ostersonntag 31.03. + 50 Tage = 20. Mai
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-05-20" in holidays


class TestGetHolidaysOstern:
    """Überprüft Oster-basierte Feiertage für verschiedene Jahre."""

    def test_karfreitag_2023(self):
        # Ostern 2023: 9. April → Karfreitag: 7. April
        holidays = get_holidays(2023, "DE", "BY")
        assert "2023-04-07" in holidays

    def test_ostermontag_2025(self):
        # Ostern 2025: 20. April → Ostermontag: 21. April
        holidays = get_holidays(2025, "DE", "BY")
        assert "2025-04-21" in holidays

    def test_verschiedene_jahre_haben_unterschiedliche_karfreitage(self):
        h2023 = get_holidays(2023, "DE", "NW")
        h2024 = get_holidays(2024, "DE", "NW")
        karfreitage = [d for d in h2023 if "Karfreitag" in h2023[d]]
        karfreitage_24 = [d for d in h2024 if "Karfreitag" in h2024[d]]
        assert karfreitage != karfreitage_24


# ---------------------------------------------------------------------------
# get_holidays – bundeslandspezifische Feiertage
# ---------------------------------------------------------------------------

# pylint: disable=too-many-public-methods
class TestGetHolidaysBundesland:
    """Überprüft bundeslandspezifische Feiertage."""

    def test_heilige_drei_koenige_bw(self):
        holidays = get_holidays(2024, "DE", "BW")
        assert "2024-01-06" in holidays

    def test_heilige_drei_koenige_by(self):
        holidays = get_holidays(2024, "DE", "BY")
        assert "2024-01-06" in holidays

    def test_heilige_drei_koenige_nicht_in_nw(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-01-06" not in holidays

    def test_frauentag_berlin(self):
        holidays = get_holidays(2024, "DE", "BE")
        assert "2024-03-08" in holidays

    def test_frauentag_mv(self):
        holidays = get_holidays(2024, "DE", "MV")
        assert "2024-03-08" in holidays

    def test_frauentag_nicht_in_by(self):
        holidays = get_holidays(2024, "DE", "BY")
        assert "2024-03-08" not in holidays

    def test_fronleichnam_nw(self):
        # Pfingstmontag 2024: 20. Mai + 10 = 30. Mai
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-05-30" in holidays

    def test_fronleichnam_by(self):
        holidays = get_holidays(2024, "DE", "BY")
        assert "2024-05-30" in holidays

    def test_fronleichnam_nicht_in_ni(self):
        holidays = get_holidays(2024, "DE", "NI")
        assert "2024-05-30" not in holidays

    def test_maria_himmelfahrt_by(self):
        # Die holidays-Bibliothek schließt Mariä Himmelfahrt in BY nicht ein,
        # da er dort nur für bestimmte Gemeinden gilt (partieller Feiertag).
        holidays = get_holidays(2024, "DE", "BY")
        assert "2024-08-15" not in holidays  # korrekt für holidays-Lib

    def test_maria_himmelfahrt_sl(self):
        holidays = get_holidays(2024, "DE", "SL")
        assert "2024-08-15" in holidays

    def test_maria_himmelfahrt_nicht_in_nw(self):
        holidays = get_holidays(2024, "DE", "NW")
        assert "2024-08-15" not in holidays

    def test_weltkindertag_th(self):
        holidays = get_holidays(2024, "DE", "TH")
        assert "2024-09-20" in holidays

    def test_weltkindertag_nicht_in_by(self):
        holidays = get_holidays(2024, "DE", "BY")
        assert "2024-09-20" not in holidays

    def test_reformationstag_bb(self):
        holidays = get_holidays(2024, "DE", "BB")
        assert "2024-10-31" in holidays

    def test_reformationstag_th(self):
        holidays = get_holidays(2024, "DE", "TH")
        assert "2024-10-31" in holidays

    def test_reformationstag_nicht_in_bw(self):
        holidays = get_holidays(2024, "DE", "BW")
        assert "2024-10-31" not in holidays

    def test_allerheiligen_bw(self):
        holidays = get_holidays(2024, "DE", "BW")
        assert "2024-11-01" in holidays

    def test_allerheiligen_nicht_in_ni(self):
        holidays = get_holidays(2024, "DE", "NI")
        assert "2024-11-01" not in holidays

    def test_buss_und_bettag_sn_ist_ein_mittwoch(self):
        # Buß- und Bettag ist immer ein Mittwoch (dayOfWeek == 3)
        holidays = get_holidays(2024, "DE", "SN")
        bub = next(d for d, n in holidays.items() if "Buß" in n)
        date = QDate.fromString(bub, "yyyy-MM-dd")
        assert date.dayOfWeek() == 3  # Mittwoch

    def test_buss_und_bettag_nur_in_sn(self):
        h_sn = get_holidays(2024, "DE", "SN")
        h_nw = get_holidays(2024, "DE", "NW")
        bub_sn = [n for n in h_sn.values() if "Buß" in n]
        bub_nw = [n for n in h_nw.values() if "Buß" in n]
        assert len(bub_sn) == 1
        assert len(bub_nw) == 0


# ---------------------------------------------------------------------------
# calculate_timed_entries – automatische Pausenberechnung
# ---------------------------------------------------------------------------

class TestCalculateTimedEntriesAutoPause:
    """Prüft die automatische Pause nach deutschem Arbeitszeitgesetz."""

    TARGET = 480   # 8 Stunden
    MAX = 600      # 10 Stunden

    def test_unter_6h_keine_pause(self):
        # 5h Arbeitszeit → 0 min Pause
        entry = make_entry(1, "08:00", "13:00")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 0
        assert total_net == 300

    def test_ueber_6h_30_min_pause(self):
        # 7h Arbeitszeit → 30 min Pause
        entry = make_entry(1, "08:00", "15:00")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 30
        assert total_net == 390  # 420 - 30

    def test_ueber_9h_45_min_pause(self):
        # 10h Arbeitszeit → 45 min Pause
        entry = make_entry(1, "08:00", "18:00")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 45
        assert total_net == 555  # 600 - 45

    def test_genau_6h_keine_pause(self):
        # Exakt 6h → Grenze: noch keine Pflichtpause
        entry = make_entry(1, "08:00", "14:00")
        results, _ = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 0

    def test_genau_9h_30_min_pause(self):
        # Exakt 9h → noch 30 min Pause (Grenze vor 45)
        entry = make_entry(1, "08:00", "17:00")
        results, _ = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 30

    def test_anwesenheit_ueber_9h_aber_arbeitszeit_unter_9h(self):
        # Anwesenheit 9h 11m (551 min). Mit 30 min Pause ist die Arbeitszeit
        # 8h 41m (< 9h) → gesetzlich genügen 30 min, NICHT 45 min.
        # Tier muss gegen die Netto-Arbeitszeit gewählt werden, nicht gegen brutto.
        entry = make_entry(1, "06:49", "16:00")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, ovt = results[1]
        assert pause == 30
        assert total_net == 521   # 551 - 30
        assert ovt == 41          # 521 - 480

    def test_anwesenheit_9h45_braucht_45_min_pause(self):
        # Anwesenheit 9h 45m (585 min): Mit nur 30 min Pause wäre die Arbeitszeit
        # 9h 15m (> 9h) → das verlangt 45 min. Also greift hier echt der 45-min-Tier.
        entry = make_entry(1, "08:00", "17:45")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 45
        assert total_net == 540   # 585 - 45

    def test_anwesenheit_knapp_ueber_9h_genau_30(self):
        # Anwesenheit 9h 30m (570 min): mit 30 min Pause Arbeitszeit 9h (= 540, nicht > 9h)
        # → 30 min reichen aus.
        entry = make_entry(1, "08:00", "17:30")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        pause, _ = results[1]
        assert pause == 30
        assert total_net == 540   # 570 - 30


class TestCalculateTimedEntriesUeberstunden:
    """Prüft die Überstunden-Berechnung."""

    TARGET = 480
    MAX = 600

    def test_positive_ueberstunden(self):
        # 10h brutto - 45 min Pause = 555 min netto → 555 - 480 = 75 min OVT
        entry = make_entry(1, "08:00", "18:00")
        results, _ = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        _, ovt = results[1]
        assert ovt == 75

    def test_negative_ueberstunden(self):
        # 7h brutto - 30 min Pause = 390 min netto → 390 - 480 = -90 min
        entry = make_entry(1, "08:00", "15:00")
        results, _ = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        _, ovt = results[1]
        assert ovt == -90

    def test_max_cap_wirkt(self):
        # 12h Eintrag → netto nach Pause = 12*60 - 45 = 675, aber max=600
        # ovt = min(600, 675) - 480 = 120
        entry = make_entry(1, "06:00", "18:00")
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=True)
        _, ovt = results[1]
        assert total_net == self.MAX
        assert ovt == self.MAX - self.TARGET

    def test_nur_letzter_eintrag_hat_ueberstunden(self):
        # 5h + 5h = 10h brutto, Lücke 1h deckt Pflichtpause → 120 min OVT
        # Nur der LETZTE Eintrag soll den OVT-Wert tragen, der erste immer 0
        e1 = make_entry(1, "08:00", "13:00")   # 300 min
        e2 = make_entry(2, "14:00", "19:00")   # 300 min, Lücke 60 min
        results, _ = calculate_timed_entries([e1, e2], self.TARGET, self.MAX, is_auto=True)
        _, ovt1 = results[1]
        _, ovt2 = results[2]
        assert ovt1 == 0
        assert ovt2 == 120   # min(600, 600) - 480


class TestCalculateTimedEntriesManuellePause:
    """Prüft manuell eingetragene Pausen (is_auto=False)."""

    TARGET = 480
    MAX = 600

    def test_manuelle_pause_wird_verwendet(self):
        entry = make_entry(1, "08:00", "16:30", pause=30)
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=False)
        pause, _ = results[1]
        assert pause == 30
        # 510 min brutto - 30 min Pause = 480 min netto
        assert total_net == 480

    def test_manuelle_pause_null(self):
        entry = make_entry(1, "08:00", "16:00", pause=0)
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=False)
        pause, _ = results[1]
        assert pause == 0
        assert total_net == 480

    def test_manuelle_pause_ignoriert_arbeitszeitgesetz(self):
        # 10h Arbeitszeit, aber manuell nur 0 min Pause eingetragen
        entry = make_entry(1, "08:00", "18:00", pause=0)
        results, total_net = calculate_timed_entries([entry], self.TARGET, self.MAX, is_auto=False)
        pause, _ = results[1]
        assert pause == 0
        assert total_net == 600  # Kein Cap hier da genau max


class TestCalculateTimedEntriesMehrereEintraege:
    """Prüft Szenarien mit mehreren Einträgen pro Tag."""

    TARGET = 480
    MAX = 600

    def test_zwei_eintraege_gesamtnetto(self):
        # 4h + 4h = 8h brutto, beide unter 6h → 0 Pause gesamt
        e1 = make_entry(1, "08:00", "12:00")
        e2 = make_entry(2, "13:00", "17:00")
        _, total_net = calculate_timed_entries([e1, e2], self.TARGET, self.MAX, is_auto=True)
        assert total_net == 480

    def test_gap_reduziert_pflichpause(self):
        # 7h brutto, aber 1h Lücke dazwischen → Lücke zählt als Pause
        # Brutto: 3h + 4h = 7h > 6h → req=30, aber gap=60 ≥ 30 → kein zusätzlicher break
        e1 = make_entry(1, "08:00", "11:00")   # 180 min
        e2 = make_entry(2, "12:00", "16:00")   # 240 min, gap=60
        results, total_net = calculate_timed_entries([e1, e2], self.TARGET, self.MAX, is_auto=True)
        pause2, _ = results[2]
        assert pause2 == 0   # Lücke deckt Pflichtpause ab
        assert total_net == 420  # 420 - 0

    def test_reihenfolge_unabhaengig_von_input_reihenfolge(self):
        # Einträge in umgekehrter Reihenfolge → gleiche Ergebnisse
        e1 = make_entry(1, "08:00", "12:00")
        e2 = make_entry(2, "13:00", "17:00")
        _, net_normal = calculate_timed_entries(
            [e1, e2], self.TARGET, self.MAX, is_auto=True
        )
        _, net_rev = calculate_timed_entries(
            [e2, e1], self.TARGET, self.MAX, is_auto=True
        )
        assert net_normal == net_rev


# ---------------------------------------------------------------------------
# is_midnight_shift / split_midnight_shift – Mitternachts-Erkennung
# ---------------------------------------------------------------------------

class TestIsMidnightShift:
    """Endzeit exakt 00:00 ist Tagesende (gleicher Tag), keine Überschreitung."""

    def test_ende_genau_mitternacht_ist_keine_ueberschreitung(self):
        # 18:00–00:00 endet am selben Tag → kein Mitternachts-Split (Regression P1)
        assert is_midnight_shift("18:00", "00:00") is False

    def test_echte_nachtschicht_ueber_mitternacht(self):
        assert is_midnight_shift("22:00", "06:00") is True

    def test_normale_tagschicht(self):
        assert is_midnight_shift("08:00", "17:00") is False

    def test_leere_oder_unvollstaendige_zeiten(self):
        assert is_midnight_shift("", "06:00") is False
        assert is_midnight_shift("22:00", "") is False

    def test_split_bei_mitternachtsende_liefert_kein_segment(self):
        # Kein leeres Folgesegment (00:00–00:00) am nächsten Tag (Regression P1)
        assert split_midnight_shift("2024-01-15", "18:00", "00:00") == (None, None)

    def test_split_echte_nachtschicht(self):
        p1, p2 = split_midnight_shift("2024-01-15", "22:00", "06:00")
        assert p1 == ("2024-01-15", "22:00", "00:00")
        assert p2 == ("2024-01-16", "00:00", "06:00")


# ---------------------------------------------------------------------------
# calculate_timed_entries – Übernacht-Schichten als EIN Eintrag (Regression P2)
# ---------------------------------------------------------------------------

class TestCalculateTimedEntriesUebernacht:
    """Eine Übernacht-Schicht wird als ein Eintrag korrekt gerechnet:
    nur EIN Tagessoll abgezogen und die Pflichtpause nicht verloren."""

    TARGET = 480   # 8 Stunden
    MAX = 600      # 10 Stunden

    def test_nachtschicht_ein_eintrag_korrektes_soll_und_pause(self):
        # 22:00–06:00 = 8h brutto → 30 min Pause → 450 netto → 450 - 480 = -30
        # (NICHT -480 wie beim fehlerhaften Aufteilen auf zwei Tage)
        entry = make_entry(1, "22:00", "06:00")
        results, total_net = calculate_timed_entries(
            [entry], self.TARGET, self.MAX, is_auto=True
        )
        pause, ovt = results[1]
        assert total_net == 450
        assert pause == 30
        assert ovt == -30

    def test_ende_mitternacht_zaehlt_zum_starttag(self):
        # 18:00–00:00 = 6h brutto, keine Pflichtpause → 360 netto → 360 - 480 = -120
        entry = make_entry(1, "18:00", "00:00")
        results, total_net = calculate_timed_entries(
            [entry], self.TARGET, self.MAX, is_auto=True
        )
        pause, ovt = results[1]
        assert total_net == 360
        assert pause == 0
        assert ovt == -120


# ---------------------------------------------------------------------------
# get_target_minutes_for_date – Soll pro Wochentag (#2)
# ---------------------------------------------------------------------------

class TestWeekdayTargets:
    """weekday_targets liefert pro Wochentag ein eigenes Soll; "" = frei (0)."""

    BASE = {"country": "DE", "state": "TH", "special_days": [], "target_work_time": "08:00"}

    def test_individuelles_wochentags_soll(self):
        # Mi (Index 2) = 6h, Sa (Index 5) = frei
        wt = ["08:00", "08:00", "06:00", "08:00", "08:00", "", ""]
        s = {**self.BASE, "weekday_targets": wt}
        assert get_target_minutes_for_date("2024-06-12", [], s) == 360  # Mittwoch
        assert get_target_minutes_for_date("2024-06-15", [], s) == 0    # Samstag (frei)

    def test_fallback_ohne_weekday_targets(self):
        # Ältere Einstellungen: workdays + Regelarbeitszeit
        s = {**self.BASE, "workdays": [0, 1, 2, 3, 4]}
        assert get_target_minutes_for_date("2024-06-12", [], s) == 480  # Mi Arbeitstag
        assert get_target_minutes_for_date("2024-06-16", [], s) == 0    # Sonntag

    def test_individuelles_soll_eines_eintrags_hat_vorrang(self):
        wt = ["08:00", "08:00", "06:00", "08:00", "08:00", "", ""]
        s = {**self.BASE, "weekday_targets": wt}
        entry = make_entry(1, "08:00", "12:00")
        entry.date = "2024-06-12"
        entry.target_minutes = 300   # individuelles Tagessoll
        assert get_target_minutes_for_date("2024-06-12", [entry], s) == 300


# ---------------------------------------------------------------------------
# get_absence_minutes – Eintragstypen-Korrektur (#1)
# ---------------------------------------------------------------------------

class TestAbsenceMinutes:
    """Urlaub/Krank/Feiertag → 0 (Saldo neutral); Gleitzeitabbau → -Soll."""

    TARGET = 480

    def test_arbeit_ist_nicht_absenz(self):
        assert get_absence_minutes(TYPE_WORK, self.TARGET) is None

    def test_urlaub_ist_saldo_neutral(self):
        assert get_absence_minutes(TYPE_VACATION, self.TARGET) == 0

    def test_krank_ist_saldo_neutral(self):
        assert get_absence_minutes(TYPE_SICK, self.TARGET) == 0

    def test_feiertag_ist_saldo_neutral(self):
        assert get_absence_minutes(TYPE_HOLIDAY, self.TARGET) == 0

    def test_gleitzeitabbau_zieht_soll_ab(self):
        assert get_absence_minutes(TYPE_FLEXTIME, self.TARGET) == -480

    def test_alle_absencen_in_menge(self):
        assert TYPE_VACATION in ABSENCE_TYPES
        assert TYPE_SICK in ABSENCE_TYPES
        assert TYPE_HOLIDAY in ABSENCE_TYPES
        assert TYPE_WORK not in ABSENCE_TYPES
        assert TYPE_FLEXTIME not in ABSENCE_TYPES
