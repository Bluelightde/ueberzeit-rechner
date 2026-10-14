"""Auswertungen für die Seiten der Server-Version -- ohne Datenbank, ohne Flask.

Jede Funktion bekommt die Einträge und Einstellungen einer Person und rechnet mit kern.py,
genau wie die Tabs der Desktop-App (Haupt-Tab, Ziel, Kalender, Statistik).
"""

import calendar
import datetime as dt
import math
from collections import defaultdict

import kern
from models import WorkEntry

WOCHENTAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
WOCHENTAGE_LANG = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober',
          'November', 'Dezember']
TYP_FARBEN = {'vacation': '#06b6d4', 'sick': '#f97316', 'holiday': '#a855f7', 'flextime': '#84cc16',
              'parental': '#ec4899'}
TYP_SYMBOLE = {'work': 'bi-briefcase', 'vacation': 'bi-sun', 'sick': 'bi-thermometer-half', 'holiday': 'bi-flag',
               'flextime': 'bi-hourglass-split', 'parental': 'bi-balloon-heart'}


def zeit(minuten, plus=False):
    """Wie format_time, aber deutsch lesbar: '+1:05 h', '-45 min'."""
    return kern.format_time(int(minuten), show_plus=plus)


def soll_fuer(datum, alle, werte, eigenes_soll=None):
    return eigenes_soll if eigenes_soll is not None else kern.get_target_minutes_for_date(datum, alle, werte)


def letzter_vor(alle, datum):
    """Zeitlich letzter Eintrag mit Endzeit vor dem Datum (wie DBManager.get_last_entry_before)."""
    kandidaten = [e for e in alle if e.date < datum and e.end]
    return max(kandidaten, key=lambda e: (e.date, e.end), default=None)


def vorschau(alle, werte, datum, start, ende, pause=0, eigenes_soll=None, ohne_id=None):
    """Live-Rechnung für das Eingabeformular (wie MainTab.update_live_calc).

    ohne_id: beim Bearbeiten der Eintrag selbst, der sonst doppelt zählte.
    """
    andere = [e for e in alle if e.id != ohne_id]
    ueberschneidung = kern.find_overlap(andere, datum, start, ende)
    if ueberschneidung is not None:
        u = ueberschneidung
        return {'ueberschneidung': f'{datum_kurz(u.date)}: {u.start}–{u.end}' + (f' ({u.reason})' if u.reason else '')}
    soll = soll_fuer(datum, alle, werte, eigenes_soll)
    max_min = kern.get_max_minutes(werte)
    auto = werte.get('auto_break', True)
    tag = [e for e in andere if e.date == datum]
    neu = WorkEntry(id=-1, date=datum, start=start, end=ende, pause=0 if auto else int(pause or 0), minutes=0,
                    reason='')
    getaktet = [e for e in tag if e.start and e.end] + [neu]
    manuell = sum(e.minutes for e in tag if not (e.start and e.end))
    ergebnis, netto = kern.calculate_timed_entries(getaktet, soll, max_min, auto, werte.get('break_rules'))
    eigene_pause, eigene_ueberstunden = ergebnis[-1]
    warnungen = []
    if netto >= max_min:
        warnungen.append(f'Maximum von {max_min // 60} h erreicht')
    vorher = letzter_vor(andere, datum)
    if vorher is not None:
        try:
            ruhe = (dt.datetime.strptime(f'{datum} {start}', '%Y-%m-%d %H:%M')
                    - dt.datetime.strptime(f'{vorher.date} {vorher.end}', '%Y-%m-%d %H:%M')).total_seconds() / 3600
            if 0 < ruhe < 11:
                warnungen.append(f'Ruhezeit nur {ruhe:.1f} h (unter 11 h)'.replace('.', ','))
        except ValueError:
            pass
    return {'pause': eigene_pause, 'ueberstunden': eigene_ueberstunden, 'netto': netto, 'soll': soll,
            'tag_saldo': netto - soll + manuell, 'warnungen': warnungen,
            'mitternacht': kern.is_midnight_shift(start, ende)}


def ende_vorschlag(alle, werte, datum, start, pause=0, eigenes_soll=None, ohne_id=None):
    """Endzeit, mit der das Tagessoll erreicht ist (wie MainTab._compute_target_end_time).

    Linear statt binär: mit automatischer Pause ist die Nettozeit nicht monoton in der Dauer
    (über 6 h springt die Pause), deshalb die erste passende Dauer von null an suchen.
    """
    beginn = kern.parse_hhmm(start)
    if beginn is None:
        return None
    andere = [e for e in alle if e.id != ohne_id]
    tag = [e for e in andere if e.date == datum]
    getaktet = [e for e in tag if e.start and e.end]
    manuell = sum(e.minutes for e in tag if not (e.start and e.end))
    soll = soll_fuer(datum, alle, werte, eigenes_soll)
    max_min = kern.get_max_minutes(werte)
    auto = werte.get('auto_break', True)
    dauer = 0
    for dauer in range(0, max_min * 2 + 1):
        neu = WorkEntry(id=-1, date=datum, start=start, end=kern.minutes_to_hhmm(beginn + dauer),
                        pause=0 if auto else int(pause or 0), minutes=0, reason='')
        _, netto = kern.calculate_timed_entries(getaktet + [neu], soll, max_min, auto, werte.get('break_rules'))
        if netto + manuell >= soll:
            break
    return kern.minutes_to_hhmm(beginn + dauer)


def saldo(alle):
    return sum(e.minutes for e in alle)


def urlaub(alle, werte, jahr):
    genommen = sum(1 for e in alle if e.entry_type == kern.TYPE_VACATION and e.date.startswith(str(jahr)))
    anspruch = int(werte.get('vacation_entitlement', 30) or 0)
    return {'genommen': genommen, 'anspruch': anspruch, 'rest': anspruch - genommen}


def ziel(alle, werte, heute):
    """Spar-Ziel (wie GoalsTab._update_goal_status). None, wenn kein Ziel aktiv ist."""
    if not werte.get('goal_active'):
        return None
    beginn = kern.parse_date(werte.get('goal_start_date', ''))
    ziel_min = int(werte.get('goal_hours', 0) or 0) * 60
    stand = saldo(alle)
    prozent = 100 if ziel_min == 0 else min(100, int(max(0, stand) / ziel_min * 100))
    erg = {'ziel': ziel_min, 'stand': stand, 'prozent': prozent, 'fehlt': max(0, ziel_min - stand),
           'beginn': beginn, 'ende': kern.parse_date(werte.get('goal_end_date', '')), 'arbeitstage': None,
           'pro_tag': None, 'zustand': ''}
    if ziel_min - stand <= 0:
        erg['zustand'] = 'erreicht'
    elif beginn is None or beginn <= heute:
        erg['zustand'] = 'begonnen'
    else:
        tage = 0
        d = heute + dt.timedelta(days=1)
        while d < beginn:
            if kern.get_target_minutes_for_date(d.isoformat(), alle, werte) > 0:
                tage += 1
            d += dt.timedelta(days=1)
        erg['arbeitstage'] = tage
        if tage == 0:
            erg['zustand'] = 'keine_tage'
        else:
            erg['zustand'] = 'unterwegs'
            erg['pro_tag'] = math.ceil((ziel_min - stand) / tage)
    return erg


def ziel_stunden(alle, werte, von, bis):
    """Sollstunden im Zeitraum, aufgerundet (wie GoalsTab._recalculate_goal_hours)."""
    if von is None or bis is None or von > bis:
        return 0
    summe, d = 0, von
    while d <= bis:
        summe += kern.get_target_minutes_for_date(d.isoformat(), alle, werte)
        d += dt.timedelta(days=1)
    return math.ceil(summe / 60)


def bloecke(alle, werte, monat=None):
    """Liste wie in der Desktop-App: mehrtägige Abwesenheiten zusammengefasst."""
    gefiltert = [e for e in alle if not monat or e.date.startswith(monat)]
    return [{'eintraege': b, 'erster': b[0], 'letzter': b[-1], 'minuten': sum(e.minutes for e in b),
             'typ': b[0].entry_type, 'ids': ','.join(str(e.id) for e in b)}
            for b in kern.consolidate_blocks(gefiltert, alle, werte)]


def woche(alle, werte, heute):
    """Die laufende Woche (Mo-So) für die Startseite: je Tag Zeiten, Art und Tag-Saldo, dazu die Summe."""
    montag = heute - dt.timedelta(days=heute.weekday())
    feiertage = {}
    for jahr in {montag.year, (montag + dt.timedelta(days=6)).year}:
        feiertage.update(kern.get_holidays(jahr, werte.get('country', 'DE'), werte.get('state')))
    tage = []
    for i in range(7):
        d = montag + dt.timedelta(days=i)
        ds = d.isoformat()
        eintraege = sorted((e for e in alle if e.date == ds), key=lambda e: e.start or '')
        arbeit = [e for e in eintraege if e.entry_type == kern.TYPE_WORK and e.start and e.end]
        anders = next((e.entry_type for e in eintraege if e.entry_type != kern.TYPE_WORK), None)
        tage.append({'datum': ds, 'name': WOCHENTAGE[i], 'tag': d.day, 'heute': d == heute,
                     'zukunft': d > heute, 'erfasst': bool(eintraege), 'minuten': sum(e.minutes for e in eintraege),
                     'zeiten': f'{arbeit[0].start}–{arbeit[-1].end}' if arbeit else '', 'typ': anders,
                     'feiertag': feiertage.get(ds),
                     'frei': kern.get_target_minutes_for_date(ds, alle, werte) == 0})
    return {'tage': tage, 'summe': sum(t['minuten'] for t in tage), 'kw': heute.isocalendar()[1]}


def bereitschaft_tage(bereitschaften):
    tage = {}
    for b in bereitschaften:
        von, bis = kern.parse_date(b.date), kern.parse_date(b.effective_end_date)
        if von is None:
            continue
        bis = bis if bis and bis >= von else von
        d = von
        while d <= bis:
            tage[d.isoformat()] = b
            d += dt.timedelta(days=1)
    return tage


def kalender(alle, bereitschaften, werte, jahr, monat, heute):
    """Monatsraster (Wochen x 7 Tage) mit Tagessaldo, Feiertag, Abwesenheit und Bereitschaft."""
    prefix = f'{jahr:04d}-{monat:02d}'
    feiertage = kern.get_holidays(jahr, werte.get('country', 'DE'), werte.get('state'))
    tag_min, tag_typ = defaultdict(int), {}
    for e in alle:
        if e.date.startswith(prefix):
            tag_min[e.date] += e.minutes
            if e.entry_type != kern.TYPE_WORK:
                tag_typ.setdefault(e.date, e.entry_type)
    hat_eintrag = {e.date for e in alle if e.date.startswith(prefix)}
    bereit = bereitschaft_tage(bereitschaften)
    wochen = []
    for woche in calendar.monthcalendar(jahr, monat):
        zeile = []
        for spalte, tag in enumerate(woche):
            if not tag:
                zeile.append(None)
                continue
            datum = dt.date(jahr, monat, tag)
            ds = datum.isoformat()
            zeile.append({'tag': tag, 'datum': ds, 'minuten': tag_min.get(ds, 0), 'erfasst': ds in hat_eintrag,
                          'typ': tag_typ.get(ds), 'feiertag': feiertage.get(ds),
                          'frei': kern.get_target_minutes_for_date(ds, alle, werte) == 0, 'heute': datum == heute,
                          'bereitschaft': ds in bereit, 'wochenende': spalte >= 5})
        wochen.append(zeile)
    return {'wochen': wochen, 'summe': sum(tag_min.values()), 'name': f'{MONATE[monat - 1]} {jahr}'}


def statistik(alle, jahr=None):
    """Kennzahlen und Monatsverlauf (wie StatsTab, Zeitraum = ein Jahr oder alles)."""
    gefiltert = [e for e in alle if e.date and (jahr is None or e.date.startswith(str(jahr)))]
    taeglich, monatlich = defaultdict(int), defaultdict(int)
    for e in gefiltert:
        taeglich[e.date] += e.minutes
        monatlich[e.date[:7]] += e.minutes
    if monatlich:
        erster, letzter = min(monatlich), max(monatlich)
        spanne = (int(letzter[:4]) - int(erster[:4])) * 12 + int(letzter[5:7]) - int(erster[5:7]) + 1
    else:
        spanne = 0
    plus_max = minus_max = plus = minus = 0
    if taeglich:
        d, ende = kern.parse_date(min(taeglich)), kern.parse_date(max(taeglich))
        while d <= ende:
            wert = taeglich.get(d.isoformat(), 0)
            plus, minus = (plus + 1, 0) if wert > 0 else ((0, minus + 1) if wert < 0 else (0, 0))
            plus_max, minus_max = max(plus_max, plus), max(minus_max, minus)
            d += dt.timedelta(days=1)
    # Monatsbalken: im Jahr alle zwölf Monate, sonst jeder erfasste Monat
    if jahr is not None:
        monate = [f'{jahr}-{m:02d}' for m in range(1, 13)]
    else:
        monate = sorted(monatlich)
    groesster = max([abs(monatlich.get(m, 0)) for m in monate] + [60])
    balken = [{'monat': m, 'name': MONATE[int(m[5:7]) - 1][:3], 'minuten': monatlich.get(m, 0),
               'anteil': abs(monatlich.get(m, 0)) / groesster} for m in monate]
    # Ø Saldo je Wochentag (wie das Diagramm der Desktop-App), mit Vorzeichen
    je_wt = defaultdict(list)
    for ds, minuten in taeglich.items():
        tag = kern.parse_date(ds)
        if tag is not None:
            je_wt[tag.weekday()].append(minuten)
    wochentage = [{'name': WOCHENTAGE[i], 'minuten': int(sum(je_wt[i]) / len(je_wt[i])) if je_wt[i] else 0,
                   'tage': len(je_wt[i])} for i in range(7)]
    groesster_wt = max([abs(w['minuten']) for w in wochentage] + [30])
    for w in wochentage:
        w['anteil'] = abs(w['minuten']) / groesster_wt
    abwesend = defaultdict(int)
    for e in gefiltert:
        if e.entry_type != kern.TYPE_WORK:
            abwesend[e.entry_type] += 1
    bester = max(monatlich.items(), key=lambda kv: kv[1], default=None)
    schlechtester = min(monatlich.items(), key=lambda kv: kv[1], default=None)
    return {'gesamt': saldo(alle), 'zeitraum': sum(monatlich.values()),
            'schnitt': int(sum(monatlich.values()) / spanne) if spanne else 0,
            'bester': bester, 'schlechtester': schlechtester, 'plus_serie': plus_max, 'minus_serie': minus_max,
            'balken': balken, 'wochentage': wochentage, 'abwesend': dict(abwesend),
            'jahre': sorted({e.date[:4] for e in alle if e.date}, reverse=True)}


def anwesend(start, ende):
    """Anwesenheitsdauer wie SessionTab._compute_duration: '8h 51m', Logout am Folgetag +24 h, sonst '—'."""
    von, bis = kern.parse_hhmm(start or ''), kern.parse_hhmm(ende or '')
    if von is None or bis is None:
        return '—'
    diff = (bis - von) % (24 * 60)
    return f'{diff // 60}h {diff % 60}m'


def datum_kurz(ds):
    d = kern.parse_date(ds)
    return d.strftime('%d.%m.%Y') if d else ds


def datum_lang(ds):
    d = kern.parse_date(ds) if isinstance(ds, str) else ds
    if not d:
        return ds or ''
    return f'{WOCHENTAGE_LANG[d.weekday()]}, {d.day}. {MONATE[d.month - 1]} {d.year}'
