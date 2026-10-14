"""
Rechenregeln ohne Oberfläche: Feiertage, Tagessoll, Pausen und Überstunden.

Gemeinsame Grundlage der Desktop-App (logic.py importiert von hier) und der
Server-Version (web/). Bewusst ohne PyQt — nur Standardbibliothek und
`holidays`, damit beide Varianten auf die Minute gleich rechnen.

Datum immer als 'yyyy-MM-dd', Uhrzeit als 'HH:mm' (Strings wie in der Datenbank).
"""
import datetime as _dt
import functools
import hashlib
import json
import logging

import holidays as holidays_lib

logger = logging.getLogger(__name__)

# --- Eintragstypen ---
TYPE_WORK = "work"
TYPE_VACATION = "vacation"
TYPE_SICK = "sick"
TYPE_HOLIDAY = "holiday"
TYPE_FLEXTIME = "flextime"
TYPE_PARENTAL = "parental"

ABSENCE_TYPES = {TYPE_VACATION, TYPE_SICK, TYPE_HOLIDAY, TYPE_PARENTAL}
ALL_TYPES = {TYPE_WORK, TYPE_VACATION, TYPE_SICK, TYPE_HOLIDAY,
             TYPE_FLEXTIME, TYPE_PARENTAL}

TYPE_LABELS = {
    TYPE_WORK: "Arbeit",
    TYPE_VACATION: "Urlaub",
    TYPE_SICK: "Krank",
    TYPE_HOLIDAY: "Feiertag",
    TYPE_FLEXTIME: "Gleitzeitabbau",
    TYPE_PARENTAL: "Elternzeit",
}

DEFAULT_BREAK_RULES = [
    {"after": 360, "break": 30},   # >6h → 30 Min (deutsches ArbZG)
    {"after": 540, "break": 45},   # >9h → 45 Min (deutsches ArbZG)
]


def parse_hhmm(text):
    """'07:30' → 450 Minuten; None bei ungültiger Angabe (wie ein ungültiges QTime)."""
    try:
        h, m = str(text).split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59) or len(str(text)) != 5:
        return None
    return h * 60 + m


def hhmm_to_minutes(text):
    """Wie parse_hhmm, aber ungültig → 0 (Verhalten von QTime.hour()*60+minute())."""
    value = parse_hhmm(text)
    return value if value is not None else 0


def minutes_to_hhmm(minutes):
    """450 → '07:30'; über Mitternacht hinaus wird umgebrochen (wie QTime.addSecs)."""
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_date(date_str):
    """'2026-10-12' → date oder None."""
    try:
        return _dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None


@functools.lru_cache(maxsize=256)
def _holidays_cached(year, country, subdiv):
    try:
        h = holidays_lib.country_holidays(country, subdiv=subdiv, years=year)
        return tuple((d.strftime("%Y-%m-%d"), name) for d, name in sorted(h.items()))
    except (KeyError, NotImplementedError) as exc:
        logger.warning("Feiertage für %s/%s konnten nicht geladen werden: %s",
                       country, subdiv, exc)
        return ()


def get_holidays(year, country, subdiv=None):
    """Gibt gesetzliche Feiertage als {yyyy-MM-dd: name} zurück.

    country: ISO 3166-1 Alpha-2 Code (z.B. 'DE', 'FR', 'US')
    subdiv:  Regions-/Bundeslandcode (z.B. 'TH' für Thüringen), oder None
    Zwischengespeichert — das Tagessoll fragt für jeden Tag einzeln nach.
    """
    return dict(_holidays_cached(year, country, subdiv or None))


# pylint: disable=too-many-locals, too-many-branches
def calculate_timed_entries(timed_entries, target_mins, max_mins, is_auto, break_rules=None):
    """Berechnet Pause und Überstunden für die Zeiteinträge eines Tages.

    Gibt ein Tupel (results, total_net) zurück:
      results    — dict {entry.id: (pause_min, overtime_min)}
      total_net  — tatsächliche Netto-Arbeitszeit des Tages (nach Cap) in Minuten

    break_rules — Liste von {"after": Minuten, "break": Minuten}, nach "after" absteigend
                  geprüft. None verwendet DEFAULT_BREAK_RULES (deutsches ArbZG).
    Nur der letzte Eintrag nach Startzeit erhält die Überstunden; alle anderen 0.
    Manuelle Einträge (ohne Start-/Endzeit) werden nicht übergeben und bleiben unberührt.
    """
    rules = sorted(
        break_rules if break_rules is not None else DEFAULT_BREAK_RULES,
        key=lambda r: r["after"], reverse=True
    )
    sorted_entries = sorted(timed_entries, key=lambda x: x.start or "00:00")
    results = {}
    total_accumulated_gross = 0
    total_accumulated_gap = 0
    recorded_pause_distributed = 0
    last_end = None

    for i, e in enumerate(sorted_entries):
        current_gross = 0
        if e.start and e.end:
            s = parse_hhmm(e.start)
            en = parse_hhmm(e.end)
            if s is not None and en is not None:
                diff = en - s
                if diff < 0:
                    diff += 24 * 60
                current_gross = diff
                if last_end is not None:
                    gap = s - last_end
                    if gap < 0:
                        gap += 24 * 60
                    total_accumulated_gap += max(0, gap)
                last_end = en
            else:
                logger.warning("Ungültige Zeitdaten in Eintrag %s, wird übersprungen", e.id)

        total_accumulated_gross += current_gross

        if is_auto:
            # ArbZG §4 staffelt die Pause nach der ARBEITSZEIT (netto), nicht nach
            # der Anwesenheit (brutto). Netto = brutto - Pause, also zirkulär.
            # Wir wählen den kleinsten Pausen-Tier, der für die daraus resultierende
            # Arbeitszeit konsistent ist (cand >= gesetzlich gefordert). Lücken (gap)
            # zählen dabei als bereits genommene Pause.
            candidates = sorted({0} | {r["break"] for r in rules})
            req = candidates[-1]
            for cand in candidates:
                total_pause = max(cand, total_accumulated_gap)
                net_work = total_accumulated_gross - total_pause
                needed = 0
                for rule in rules:
                    if net_work > rule["after"]:
                        needed = rule["break"]
                        break
                if cand >= needed:
                    req = cand
                    break
            current_total_pause_needed = max(0, req - total_accumulated_gap)
            current_break = max(0, current_total_pause_needed - recorded_pause_distributed)
        else:
            current_break = e.pause

        if i == len(sorted_entries) - 1:
            total_net = total_accumulated_gross - (recorded_pause_distributed + current_break)
            ovt = int(min(max_mins, total_net) - target_mins)
        else:
            ovt = 0

        results[e.id] = (int(current_break), ovt)
        recorded_pause_distributed += current_break

    total_net = min(max_mins, total_accumulated_gross - recorded_pause_distributed)
    return results, total_net


def get_absence_minutes(entry_type, target_minutes):
    """Berechnet den Überstunden-Effekt eines Nicht-Arbeits-Eintrags.

    Urlaub/Krank/Feiertag (ABSENCE_TYPES): der Tag zählt als erledigt,
    0 Überstunden (Saldo unverändert).

    Gleitzeitabbau (flextime): die Soll-Stunden werden vom Saldo abgezogen
    (Überstunden „ausgeben", z. B. für einen freien Tag).
    """
    if entry_type == TYPE_FLEXTIME:
        return -target_minutes
    if entry_type in ABSENCE_TYPES:
        return 0
    return None   # "work" → normale Zeitrechnung


def format_time(total_minutes, show_plus=False):
    """Formatiert Minuten in lesbare Zeitangabe.
    Unter 60 Min → '45m', ab 60 Min → '1h 5m'.
    """
    sign = "+" if show_plus and total_minutes > 0 else ("-" if total_minutes < 0 else "")
    abs_m = abs(total_minutes)
    if abs_m < 60:
        return f"{sign}{abs_m}m"
    return f"{sign}{abs_m // 60}h {abs_m % 60}m"


def get_target_minutes(settings):
    """Gibt die Regelarbeitszeit aus den Einstellungen in Minuten zurück."""
    return hhmm_to_minutes(settings.get("target_work_time", "08:00"))


def get_max_minutes(settings):
    """Gibt die maximal anrechenbare Arbeitszeit pro Tag in Minuten zurück."""
    return settings.get("max_work_hours", 10) * 60


def get_target_minutes_for_date(date_str, entries, settings):  # pylint: disable=too-many-return-statements
    """Ermittelt das Tagessoll für ein bestimmtes Datum.

    Prüft in dieser Reihenfolge:
    1. Individuelles Tagessoll eines vorhandenen Eintrags
    2. Sonderarbeitstage aus den Einstellungen (z.B. 24.12.)
    3. Feiertag → 0 Minuten
    4. Kein Arbeitstag (Wochenende) → 0 Minuten
    5. Reguläre Regelarbeitszeit
    """
    for e in entries:
        if e.date == date_str and e.target_minutes != -1:
            return e.target_minutes

    day = parse_date(date_str)
    if day is None:
        # Ungültiges Datum: wie ein ungültiges QDate → kein Arbeitstag
        return 0

    for sd in settings.get("special_days", []):
        if day.month == sd["month"] and day.day == sd["day"]:
            return hhmm_to_minutes(sd["target"])

    holidays = get_holidays(day.year, settings.get("country", "DE"), settings.get("state"))
    if date_str in holidays:
        return 0

    day_idx = day.weekday()   # Mo = 0 (wie QDate.dayOfWeek() - 1)
    weekday_targets = settings.get("weekday_targets")
    if isinstance(weekday_targets, list) and len(weekday_targets) == 7:
        val = weekday_targets[day_idx]
        if not val:
            return 0
        return hhmm_to_minutes(val)

    # Fallback (alte Einstellungen ohne weekday_targets)
    workdays = settings.get("workdays", [0, 1, 2, 3, 4])
    if day_idx not in workdays:
        return 0
    return get_target_minutes(settings)


def is_midnight_shift(start_str: str, end_str: str) -> bool:
    """Prüft, ob eine Zeitspanne über Mitternacht geht (Endzeit vor Startzeit)."""
    if not start_str or not end_str:
        return False
    s = parse_hhmm(start_str)
    e = parse_hhmm(end_str)
    if s is None or e is None:
        return False
    # Endzeit exakt um Mitternacht ist das Tagesende desselben Tages, keine
    # Überschreitung — andernfalls erzeugt split_midnight_shift ein leeres
    # Folgesegment (00:00–00:00) mit Phantom-Soll am nächsten Tag.
    if end_str == "00:00":
        return False
    return e < s


def split_midnight_shift(date_str: str, start_str: str, end_str: str):
    """Teilt eine Mitternachtsschicht in zwei Teile auf.

    Gibt ein Tupel ((date1, start1, end1), (date2, start2, end2)) zurück.
    Wenn keine Mitternachtsschicht vorliegt, wird (None, None) zurückgegeben.
    """
    if not is_midnight_shift(start_str, end_str):
        return None, None
    d1 = parse_date(date_str)
    if d1 is None:
        return None, None
    d2 = d1 + _dt.timedelta(days=1)
    part1 = (d1.isoformat(), start_str, "00:00")
    part2 = (d2.isoformat(), "00:00", end_str)
    return part1, part2


def segment_overlap(entries, date_str, start_str, end_str, exclude_id=None):
    """Erster bestehender Zeiteintrag am Tag, der [start, end) schneidet, sonst None.

    Ende 00:00 bzw. Ende vor Start zählt als Tagesende (24:00).
    """
    s_new = hhmm_to_minutes(start_str)
    e_new = hhmm_to_minutes(end_str)
    if e_new <= s_new and end_str == "00:00":
        e_new = 24 * 60
    for e in entries:
        if e.date == date_str and e.start and e.end and e.id != exclude_id:
            s_old = hhmm_to_minutes(e.start)
            e_old = hhmm_to_minutes(e.end)
            if e_old <= s_old:
                e_old = 24 * 60
            if s_new < e_old and s_old < e_new:
                return e
    return None


def find_overlap(entries, date_str, start_str, end_str, exclude_id=None):
    """Wie segment_overlap, teilt Mitternachtsschichten aber in zwei Segmente."""
    if not start_str or not end_str:
        return None
    if is_midnight_shift(start_str, end_str):
        p1, p2 = split_midnight_shift(date_str, start_str, end_str)
        return (segment_overlap(entries, *p1, exclude_id=exclude_id)
                or segment_overlap(entries, *p2, exclude_id=exclude_id))
    return segment_overlap(entries, date_str, start_str, end_str, exclude_id=exclude_id)


def recalculate_day(date_str, entries, settings):
    """Verteilt Pausen und Überstunden für alle Einträge eines Tages neu.

    Gleiche Regeln wie MainTab.recalculate_day der Desktop-App, aber ohne
    Datenbank: ändert die Objekte in `entries` und gibt die geänderten zurück.
    Manuelle Einträge (Arbeit ohne Start-/Endzeit) bleiben unberührt.
    """
    day_entries = [e for e in entries if e.date == date_str]
    if not day_entries:
        return []
    target_mins = get_target_minutes_for_date(date_str, entries, settings)
    changed = []
    for e in day_entries:
        if e.entry_type in ABSENCE_TYPES or e.entry_type == TYPE_FLEXTIME:
            e.minutes = get_absence_minutes(e.entry_type, target_mins)
            e.pause = 0
            changed.append(e)
    timed = [e for e in day_entries if e.start and e.end and e.entry_type == TYPE_WORK]
    if timed:
        results, _ = calculate_timed_entries(
            timed, target_mins, get_max_minutes(settings),
            settings.get("auto_break", True), settings.get("break_rules"))
        for e in timed:
            e.pause, e.minutes = results[e.id]
            changed.append(e)
    return changed


def only_nonworkdays_between(date_a, date_b, entries, settings):
    """True, wenn jeder Kalendertag STRIKT zwischen date_a und date_b ein
    Nicht-Arbeitstag ist (Tagessoll 0 → Wochenende/Feiertag)."""
    a, b = parse_date(date_a), parse_date(date_b)
    if a is None or b is None:
        return False
    d = a + _dt.timedelta(days=1)
    while d < b:
        if get_target_minutes_for_date(d.isoformat(), entries, settings) > 0:
            return False
        d += _dt.timedelta(days=1)
    return True


def consolidate_blocks(entries, all_entries, settings):
    """Fasst aufeinanderfolgende, gleichartige Abwesenheiten zu Blöcken zusammen
    (Nicht-Arbeitstage dazwischen werden überbrückt). Arbeitseinträge bleiben
    einzeln. Blöcke absteigend nach Startdatum, innerhalb aufsteigend."""
    asc = sorted(entries, key=lambda e: (e.date, e.start or ""))
    blocks = []
    for e in asc:
        etype = getattr(e, "entry_type", TYPE_WORK)
        if etype != TYPE_WORK and blocks:
            prev = blocks[-1]
            if (getattr(prev[-1], "entry_type", TYPE_WORK) == etype
                    and only_nonworkdays_between(prev[-1].date, e.date, all_entries, settings)):
                prev.append(e)
                continue
        blocks.append([e])
    blocks.sort(key=lambda b: (b[0].date, b[0].start or ""), reverse=True)
    return blocks


# --- Abgleich Desktop <-> Server ---------------------------------------------------------
# Abgeglichen wird je Tag: alle Einträge und Bereitschaften eines Datums zusammen (Pause und
# Überstunden hängen ohnehin am ganzen Tag). Beide Seiten bilden daraus mit denselben Regeln
# einen Fingerabdruck; ein leerer Tag hat den Fingerabdruck "".

MAX_JE_TAG = 50          # Einträge bzw. Bereitschaften je Tag, mehr nimmt der Abgleich nicht an
_MAX_TEXT = 500


def _ganzzahl(wert, leer=0):
    return leer if wert is None or wert == "" else int(wert)


def tag_inhalt(eintraege=(), bereitschaften=()):
    """Einträge/Bereitschaften EINES Tages (WorkEntry/BereitschaftEntry) -> kanonische Form.

    Reihenfolge und Datenbank-IDs spielen keine Rolle, leere Werte werden vereinheitlicht."""
    e = [{"start": x.start or "", "end": x.end or "", "pause": _ganzzahl(x.pause),
          "minutes": _ganzzahl(x.minutes), "reason": x.reason or "",
          "target_minutes": _ganzzahl(x.target_minutes, -1), "type": x.entry_type or TYPE_WORK}
         for x in eintraege]
    b = [{"start": x.start or "", "end": x.end or "", "note": x.note or "",
          "end_date": x.end_date or ""} for x in bereitschaften]

    def ordnen(liste):
        return sorted(liste, key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))

    return {"eintraege": ordnen(e), "bereitschaft": ordnen(b)}


def tag_hash(inhalt):
    """Fingerabdruck eines Tages aus tag_inhalt(); "" für einen leeren Tag."""
    if not inhalt.get("eintraege") and not inhalt.get("bereitschaft"):
        return ""
    text = json.dumps(inhalt, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tage_gruppieren(eintraege, bereitschaften):
    """Alle Einträge/Bereitschaften -> {datum: tag_inhalt} (nur Tage mit Inhalt)."""
    je_tag = {}
    for x in eintraege:
        je_tag.setdefault(x.date, ([], []))[0].append(x)
    for x in bereitschaften:
        je_tag.setdefault(x.date, ([], []))[1].append(x)
    return {d: tag_inhalt(e, b) for d, (e, b) in je_tag.items()}


def tag_inhalt_pruefen(inhalt):
    """Von der anderen Seite empfangenen Tag prüfen -> kanonische Form; ValueError bei Unsinn."""
    if not isinstance(inhalt, dict):
        raise ValueError("Tag ist kein Objekt")
    eintraege, bereitschaften = inhalt.get("eintraege", []), inhalt.get("bereitschaft", [])
    if not isinstance(eintraege, list) or not isinstance(bereitschaften, list) \
            or len(eintraege) > MAX_JE_TAG or len(bereitschaften) > MAX_JE_TAG:
        raise ValueError("Einträge fehlen oder sind zu viele")

    def zeit(wert):
        if wert in ("", None):
            return ""
        if parse_hhmm(wert) is None:
            raise ValueError(f"Ungültige Uhrzeit: {wert!r}")
        return wert

    def text(wert):
        if wert is None:
            return ""
        if not isinstance(wert, str) or len(wert) > _MAX_TEXT:
            raise ValueError("Ungültiger Text")
        return wert

    def zahl(wert, leer, grenze):
        if isinstance(wert, bool):
            raise ValueError("Ungültige Zahl")
        z = _ganzzahl(wert, leer)
        if not -grenze <= z <= grenze:
            raise ValueError(f"Zahl außerhalb des Bereichs: {z}")
        return z

    e_neu = []
    for x in eintraege:
        if not isinstance(x, dict) or x.get("type", TYPE_WORK) not in ALL_TYPES:
            raise ValueError("Ungültiger Eintrag")
        e_neu.append({"start": zeit(x.get("start")), "end": zeit(x.get("end")),
                      "pause": zahl(x.get("pause"), 0, 24 * 60),
                      "minutes": zahl(x.get("minutes"), 0, 100000), "reason": text(x.get("reason")),
                      "target_minutes": zahl(x.get("target_minutes"), -1, 24 * 60),
                      "type": x.get("type", TYPE_WORK)})
    b_neu = []
    for x in bereitschaften:
        if not isinstance(x, dict):
            raise ValueError("Ungültige Bereitschaft")
        bis = text(x.get("end_date"))
        if bis and parse_date(bis) is None:
            raise ValueError(f"Ungültiges Datum: {bis!r}")
        b_neu.append({"start": zeit(x.get("start")), "end": zeit(x.get("end")),
                      "note": text(x.get("note")), "end_date": bis})
    def ordnen(liste):
        return sorted(liste, key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))

    return {"eintraege": ordnen(e_neu), "bereitschaft": ordnen(b_neu)}
