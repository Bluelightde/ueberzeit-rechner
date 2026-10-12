"""Datenbank der Server-Version: Benutzer, Einstellungen und Einträge je Benutzer.

Die Einträge haben dieselben Spalten wie in der Desktop-App (ueberstunden_daten.db),
nur mit `benutzer_id` davor -- so geht der Austausch (austausch.py) ohne Umrechnen.
Gerechnet wird ausschließlich mit kern.py, genau wie auf dem Desktop.
"""

import copy
import json
import sqlite3

from flask import current_app, g

import kern
from models import BereitschaftEntry, WorkEntry

SCHEMA_VERSION = 1

# Voreinstellungen wie in der Desktop-App (main.py), ohne die rein lokalen Schalter
# (Anmeldezeit des Rechners, Datenbankpfad, Sprache).
STANDARD = {
    "default_start": "07:00",
    "target_work_time": "08:00",
    "country": "DE",
    "state": "TH",
    "break_rules": [{"after": 360, "break": 30}, {"after": 540, "break": 45}],
    "auto_break": True,
    "max_work_hours": 10,
    "workdays": [0, 1, 2, 3, 4],
    "weekday_targets": ["08:00", "08:00", "08:00", "08:00", "08:00", "", ""],
    "vacation_entitlement": 30,
    "special_days": [{"month": 12, "day": 24, "target": "04:00"},
                     {"month": 12, "day": 31, "target": "04:00"}],
    "goal_active": False,
    "goal_start_date": "",
    "goal_end_date": "",
    "goal_hours": 0,
}

# Diese Schlüssel einer Desktop-Einstellungsdatei werden übernommen (Rest ist gerätebezogen).
UEBERNEHMEN = set(STANDARD) | {"theme"}


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATENBANK'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode = WAL')
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def schliessen(_fehler=None):
    verbindung = g.pop('db', None)
    if verbindung is not None:
        verbindung.close()


def schema_anlegen():
    """Stufenweise über PRAGMA user_version (wie in den anderen Apps). Nie eine alte Stufe ändern."""
    d = db()
    version = d.execute('PRAGMA user_version').fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    if version < 1:
        d.executescript('''
            CREATE TABLE IF NOT EXISTS benutzer (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                pw_hash TEXT NOT NULL,                   -- '!' = nur Anmeldung über Authentik
                admin INTEGER NOT NULL DEFAULT 0,
                oidc_sub TEXT UNIQUE,
                sitzung INTEGER NOT NULL DEFAULT 0,      -- erhöhen = alle Sitzungen dieses Benutzers enden
                erstellt TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS anmeldeversuche (
                schluessel TEXT NOT NULL,
                zeit REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS einstellungen (
                benutzer_id INTEGER PRIMARY KEY REFERENCES benutzer(id) ON DELETE CASCADE,
                json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benutzer_id INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                start TEXT,
                end TEXT,
                pause INTEGER,
                minutes INTEGER,
                reason TEXT,
                target_minutes INTEGER DEFAULT -1,
                type TEXT NOT NULL DEFAULT 'work'
            );
            CREATE INDEX IF NOT EXISTS entries_benutzer_datum ON entries (benutzer_id, date);
            CREATE TABLE IF NOT EXISTS bereitschaft_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benutzer_id INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                start TEXT,
                end TEXT,
                note TEXT,
                end_date TEXT
            );
            CREATE INDEX IF NOT EXISTS bereitschaft_benutzer ON bereitschaft_entries (benutzer_id, date);
        ''')
    d.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    d.commit()


# --- Einstellungen ------------------------------------------------------------

def einstellungen(benutzer_id):
    """Einstellungen einer Person (Voreinstellungen ergänzt, Ergebnis frei veränderbar)."""
    zeile = db().execute('SELECT json FROM einstellungen WHERE benutzer_id = ?', (benutzer_id,)).fetchone()
    werte = copy.deepcopy(STANDARD)
    if zeile:
        try:
            werte.update(json.loads(zeile['json']))
        except ValueError:
            pass
    return werte


def einstellungen_speichern(benutzer_id, werte):
    gespeichert = {k: v for k, v in werte.items() if k in UEBERNEHMEN or k == 'laufend'}
    db().execute('INSERT INTO einstellungen VALUES (?, ?) ON CONFLICT(benutzer_id) DO UPDATE SET json = excluded.json',
                 (benutzer_id, json.dumps(gespeichert, ensure_ascii=False)))


# --- Einträge -------------------------------------------------------------------

_SPALTEN = 'id, date, start, end, pause, minutes, reason, target_minutes, type'


def _eintrag(zeile):
    return WorkEntry(zeile['id'], zeile['date'], zeile['start'] or '', zeile['end'] or '', zeile['pause'] or 0,
                     zeile['minutes'] or 0, zeile['reason'] or '',
                     -1 if zeile['target_minutes'] is None else zeile['target_minutes'], zeile['type'] or 'work')


def eintraege(benutzer_id):
    """Alle Einträge, neueste zuerst (wie DBManager.load_all)."""
    zeilen = db().execute(f'SELECT {_SPALTEN} FROM entries WHERE benutzer_id = ? ORDER BY date DESC, start DESC',
                          (benutzer_id,)).fetchall()
    return [_eintrag(z) for z in zeilen]


def eintrag(benutzer_id, eintrag_id):
    zeile = db().execute(f'SELECT {_SPALTEN} FROM entries WHERE benutzer_id = ? AND id = ?',
                         (benutzer_id, eintrag_id)).fetchone()
    return _eintrag(zeile) if zeile else None


def eintrag_anlegen(benutzer_id, e):
    e.id = db().execute(
        'INSERT INTO entries (benutzer_id, date, start, end, pause, minutes, reason, target_minutes, type) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (benutzer_id, e.date, e.start, e.end, e.pause, e.minutes, e.reason, e.target_minutes, e.entry_type)).lastrowid
    return e


def eintrag_aendern(benutzer_id, e):
    db().execute('UPDATE entries SET date = ?, start = ?, end = ?, pause = ?, minutes = ?, reason = ?, '
                 'target_minutes = ?, type = ? WHERE id = ? AND benutzer_id = ?',
                 (e.date, e.start, e.end, e.pause, e.minutes, e.reason, e.target_minutes, e.entry_type, e.id,
                  benutzer_id))


def eintrag_loeschen(benutzer_id, eintrag_id):
    db().execute('DELETE FROM entries WHERE id = ? AND benutzer_id = ?', (eintrag_id, benutzer_id))


def tage_neu_berechnen(benutzer_id, tage, alle=None, werte=None):
    """Rechnet die genannten Tage neu und speichert die geänderten Einträge (ohne commit)."""
    alle = eintraege(benutzer_id) if alle is None else alle
    werte = einstellungen(benutzer_id) if werte is None else werte
    for tag in sorted(set(tage)):
        for e in kern.recalculate_day(tag, alle, werte):
            eintrag_aendern(benutzer_id, e)
    return alle


def alles_neu_berechnen(benutzer_id):
    """Nach geänderten Einstellungen: jeder Tag neu (wie recalculate_all_days)."""
    alle = eintraege(benutzer_id)
    tage_neu_berechnen(benutzer_id, {e.date for e in alle}, alle)


# --- Bereitschaft -------------------------------------------------------------------

def bereitschaften(benutzer_id):
    zeilen = db().execute('SELECT id, date, start, end, note, end_date FROM bereitschaft_entries '
                          'WHERE benutzer_id = ? ORDER BY date DESC, start DESC', (benutzer_id,)).fetchall()
    return [BereitschaftEntry(z['id'], z['date'], z['start'] or '', z['end'] or '', z['note'] or '',
                              z['end_date'] or '') for z in zeilen]


def bereitschaft_anlegen(benutzer_id, b):
    b.id = db().execute('INSERT INTO bereitschaft_entries (benutzer_id, date, start, end, note, end_date) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (benutzer_id, b.date, b.start, b.end, b.note, b.end_date)).lastrowid
    return b


def bereitschaft_loeschen(benutzer_id, b_id):
    db().execute('DELETE FROM bereitschaft_entries WHERE id = ? AND benutzer_id = ?', (b_id, benutzer_id))
