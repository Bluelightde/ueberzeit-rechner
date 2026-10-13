"""Austausch mit der Desktop-App: deren Datenbank und Einstellungen einlesen, eine Datenbank im
Desktop-Format und CSV ausgeben.

🔑 Die Desktop-Datenbank (ueberstunden_daten.db) wird nur LESEND geöffnet (mode=ro) und vorher geprüft
   (SQLite-Kopf, quick_check, Tabelle entries). Ältere Desktop-Stände ohne die Spalten target_minutes/type
   bzw. end_date gehen auch -- es gelten dann dieselben Vorgaben wie bei der Migration auf dem Desktop.
"""

import csv
import io
import json
import os
import sqlite3
import tempfile

import kern
from models import BereitschaftEntry, WorkEntry

DESKTOP_SCHEMA_VERSION = 3      # database.SCHEMA_VERSION der Desktop-App
SQLITE_KOPF = b'SQLite format 3\x00'


class AustauschFehler(Exception):
    pass


def _spalten(verbindung, tabelle):
    return {z[1] for z in verbindung.execute(f'PRAGMA table_info({tabelle})')}


def desktop_db_lesen(inhalt):
    """Bytes einer ueberstunden_daten.db -> (eintraege, bereitschaften, anwesenheit). Wirft AustauschFehler."""
    if not inhalt.startswith(SQLITE_KOPF):
        raise AustauschFehler('Das ist keine Datenbank der Desktop-App (ueberstunden_daten.db).')
    fd, pfad = tempfile.mkstemp(suffix='.db')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(inhalt)
        v = sqlite3.connect(f'file:{pfad}?mode=ro', uri=True)
        try:
            if v.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise AustauschFehler('Die Datenbank ist beschädigt.')
            spalten = _spalten(v, 'entries')
            if not {'date', 'start', 'end', 'pause', 'minutes', 'reason'} <= spalten:
                raise AustauschFehler('In der Datei fehlt die Tabelle mit den Einträgen.')
            ziel = "target_minutes" if 'target_minutes' in spalten else "-1"
            typ = "type" if 'type' in spalten else "'work'"
            eintraege = []
            for z in v.execute(f'SELECT date, start, end, pause, minutes, reason, {ziel}, {typ} FROM entries '
                               'ORDER BY date, start'):
                datum = (z[0] or '').strip()
                if kern.parse_date(datum) is None:
                    continue
                art = z[7] if z[7] in kern.ALL_TYPES else kern.TYPE_WORK
                eintraege.append(WorkEntry(None, datum, z[1] or '', z[2] or '', int(z[3] or 0), int(z[4] or 0),
                                           z[5] or '', -1 if z[6] is None else int(z[6]), art))
            bereitschaften = []
            b_spalten = _spalten(v, 'bereitschaft_entries')
            if {'date', 'start', 'end', 'note'} <= b_spalten:
                bis = 'end_date' if 'end_date' in b_spalten else "''"
                for z in v.execute(f'SELECT date, start, end, note, {bis} FROM bereitschaft_entries ORDER BY date'):
                    if kern.parse_date(z[0] or '') is not None:
                        bereitschaften.append(BereitschaftEntry(None, z[0], z[1] or '', z[2] or '', z[3] or '',
                                                                z[4] or ''))
            anwesenheit = []
            if {'date', 'start_time'} <= _spalten(v, 'device_login'):
                bis = 'end_time' if 'end_time' in _spalten(v, 'device_login') else "''"
                for z in v.execute(f'SELECT date, start_time, {bis} FROM device_login ORDER BY date'):
                    tag = anwesenheit_pruefen(z[0], z[1], z[2])
                    if tag:
                        anwesenheit.append(tag)
            return eintraege, bereitschaften, anwesenheit
        except sqlite3.DatabaseError as e:
            raise AustauschFehler(f'Die Datei lässt sich nicht lesen: {e}') from e
        finally:
            v.close()
    finally:
        os.unlink(pfad)


def anwesenheit_pruefen(datum, login, logout):
    """Ein Tag Anwesenheit (Desktop-Datenbank oder Meldung der Desktop-App) -> (datum, login, logout) oder None."""
    datum = datum.strip() if isinstance(datum, str) else ''
    if kern.parse_date(datum) is None:
        return None
    login = login if isinstance(login, str) and kern.parse_hhmm(login) is not None else ''
    logout = logout if isinstance(logout, str) and kern.parse_hhmm(logout) is not None else ''
    return (datum, login, logout) if login or logout else None


def desktop_einstellungen_lesen(inhalt, erlaubt):
    """Bytes einer ueberstunden_settings.json -> nur die übernehmbaren Schlüssel, geprüft."""
    try:
        roh = json.loads(inhalt.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as e:
        raise AustauschFehler('Die Einstellungsdatei ist kein gültiges JSON.') from e
    if not isinstance(roh, dict):
        raise AustauschFehler('Die Einstellungsdatei hat ein unbekanntes Format.')
    werte = {k: v for k, v in roh.items() if k in erlaubt}
    return pruefen(werte)


def pruefen(werte):
    """Typen der Einstellungen absichern (Datei oder Formular), Unbrauchbares weglassen."""
    sauber = {}
    for k in ('default_start', 'target_work_time'):
        if k in werte and kern.parse_hhmm(werte[k]) is not None:
            sauber[k] = werte[k]
    if isinstance(werte.get('country'), str) and len(werte['country']) == 2:
        sauber['country'] = werte['country'].upper()
    if 'state' in werte:
        sauber['state'] = werte['state'] if isinstance(werte['state'], str) and len(werte['state']) <= 3 else None
    for k in ('auto_break', 'goal_active', 'use_login_time'):
        if k in werte:
            sauber[k] = bool(werte[k])
    for k, unten, oben in (('max_work_hours', 1, 24), ('vacation_entitlement', 0, 366), ('goal_hours', 0, 100000)):
        try:
            if k in werte:
                sauber[k] = max(unten, min(oben, int(werte[k])))
        except (TypeError, ValueError):
            pass
    if isinstance(werte.get('workdays'), list):
        sauber['workdays'] = sorted({int(t) for t in werte['workdays'] if isinstance(t, int) and 0 <= t <= 6})
    wt = werte.get('weekday_targets')
    if isinstance(wt, list) and len(wt) == 7:
        sauber['weekday_targets'] = [t if isinstance(t, str) and kern.parse_hhmm(t) is not None else '' for t in wt]
    if isinstance(werte.get('special_days'), list):
        tage = []
        for sd in werte['special_days']:
            try:
                tag, monat = int(sd['day']), int(sd['month'])
            except (KeyError, TypeError, ValueError):
                continue
            if 1 <= tag <= 31 and 1 <= monat <= 12 and kern.parse_hhmm(sd.get('target')) is not None:
                tage.append({'day': tag, 'month': monat, 'target': sd['target']})
        sauber['special_days'] = tage
    if isinstance(werte.get('break_rules'), list):
        regeln = []
        for r in werte['break_rules']:
            try:
                nach, pause = int(r['after']), int(r['break'])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= nach <= 24 * 60 and 0 <= pause <= 240:
                regeln.append({'after': nach, 'break': pause})
        sauber['break_rules'] = regeln
    for k in ('goal_start_date', 'goal_end_date'):
        if k in werte and (werte[k] == '' or kern.parse_date(werte[k]) is not None):
            sauber[k] = werte[k]
    if werte.get('theme') in ('light', 'dark', 'auto'):
        sauber['theme'] = werte['theme']
    return sauber


def desktop_db_schreiben(eintraege, bereitschaften, anwesenheit=()):
    """Datenbank im Format der Desktop-App (Schema 3) als Bytes -- dort unter
    Einstellungen -> Datenbank-Speicherort auswählen oder als Sicherung einspielen."""
    fd, pfad = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        v = sqlite3.connect(pfad)
        v.executescript('''
            CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, start TEXT, end TEXT,
                pause INTEGER, minutes INTEGER, reason TEXT, target_minutes INTEGER DEFAULT -1,
                type TEXT NOT NULL DEFAULT 'work');
            CREATE TABLE bereitschaft_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, start TEXT,
                end TEXT, note TEXT, end_date TEXT);
            CREATE TABLE device_login (date TEXT PRIMARY KEY, start_time TEXT NOT NULL, end_time TEXT);
        ''')
        v.executemany('INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes, type) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                      [(e.date, e.start, e.end, e.pause, e.minutes, e.reason, e.target_minutes, e.entry_type)
                       for e in sorted(eintraege, key=lambda e: (e.date, e.start or ''))])
        v.executemany('INSERT INTO bereitschaft_entries (date, start, end, note, end_date) VALUES (?, ?, ?, ?, ?)',
                      [(b.date, b.start, b.end, b.note, b.end_date) for b in sorted(bereitschaften,
                                                                                   key=lambda b: b.date)])
        v.executemany('INSERT INTO device_login (date, start_time, end_time) VALUES (?, ?, ?)',
                      [(a['date'], a['start'], a['end']) for a in anwesenheit])
        v.execute(f'PRAGMA user_version = {DESKTOP_SCHEMA_VERSION}')
        v.commit()
        v.close()
        with open(pfad, 'rb') as f:
            return f.read()
    finally:
        os.unlink(pfad)


def csv_schreiben(eintraege):
    """CSV wie der Export der Desktop-App (Semikolon, Datum, Zeitraum, Minuten, Dauer, Anlass)."""
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=';')
    w.writerow(['Datum', 'Zeitraum', 'Minuten', 'Dauer', 'Anlass'])
    for e in sorted(eintraege, key=lambda e: (e.date, e.start or '')):
        d = kern.parse_date(e.date)
        if e.entry_type != kern.TYPE_WORK:
            zeitraum = kern.TYPE_LABELS.get(e.entry_type, e.entry_type)
        elif e.start and e.end:
            zeitraum = f'{e.start} - {e.end}' + (f' (-{e.pause}m)' if e.pause else '')
        else:
            zeitraum = '-'
        w.writerow([d.strftime('%d.%m.%y') if d else e.date, zeitraum, e.minutes, kern.format_time(e.minutes),
                    e.reason])
    w.writerow(['Gesamt', '', '', kern.format_time(sum(e.minutes for e in eintraege)), ''])
    return '﻿' + puffer.getvalue()     # BOM: Excel erkennt sonst die Umlaute nicht
