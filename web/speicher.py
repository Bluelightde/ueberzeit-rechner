"""Datenbank der Server-Version: Benutzer, Einstellungen und Einträge je Benutzer.

Die Einträge haben dieselben Spalten wie in der Desktop-App (ueberstunden_daten.db),
nur mit `benutzer_id` davor -- so geht der Austausch (austausch.py) ohne Umrechnen.
Gerechnet wird ausschließlich mit kern.py, genau wie auf dem Desktop.
"""

import copy
import hashlib
import json
import secrets
import sqlite3

from flask import current_app, g

import kern
from models import BereitschaftEntry, WorkEntry

SCHEMA_VERSION = 3

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
    "special_days": [{"month": 12, "day": 24, "target": "04:00"},
                     {"month": 12, "day": 31, "target": "04:00"}],
    "goal_active": False,
    "goal_start_date": "",
    "goal_end_date": "",
    "goal_hours": 0,
    "use_login_time": True,     # Anmeldezeit des Rechners (von der Desktop-App gemeldet) als Startvorschlag
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
    if version < 2:
        # Anwesenheit wie device_login der Desktop-App, je Person; Geräte = Zugänge der Desktop-App (nur Hash)
        d.executescript('''
            CREATE TABLE IF NOT EXISTS anwesenheit (
                benutzer_id INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL DEFAULT '',
                end_time TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (benutzer_id, date)
            );
            CREATE TABLE IF NOT EXISTS geraete (
                id INTEGER PRIMARY KEY,
                benutzer_id INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                erstellt TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                zuletzt TEXT
            );
        ''')
    if version < 3:
        # Abgleich mit der Desktop-App: wann wurde ein Tag zuletzt geändert (UTC, ISO)? Trigger erfassen jede
        # Änderung an Einträgen und Bereitschaften -- auch Austausch und Neuberechnung, ohne Code daran zu hängen.
        d.executescript('''
            CREATE TABLE IF NOT EXISTS tag_stand (
                benutzer_id INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                geaendert TEXT NOT NULL,
                PRIMARY KEY (benutzer_id, date)
            );
        ''' + _trigger('entries', 'start, end, pause, minutes, reason, target_minutes, type')
          + _trigger('bereitschaft_entries', 'start, end, note, end_date'))
    d.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    d.commit()


JETZT_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _trigger(tabelle, spalten):
    """Trigger, die bei jeder echten Änderung an `tabelle` den Tag in tag_stand als geändert markieren."""
    markieren = ('INSERT OR REPLACE INTO tag_stand (benutzer_id, date, geaendert) '
                 f'VALUES ({{z}}.benutzer_id, {{z}}.date, {JETZT_SQL});')
    anders = ' OR '.join(f'OLD.{sp.strip()} IS NOT NEW.{sp.strip()}' for sp in ('date, ' + spalten).split(','))
    return f'''
        CREATE TRIGGER IF NOT EXISTS {tabelle}_neu AFTER INSERT ON {tabelle}
        BEGIN {markieren.format(z='NEW')} END;
        CREATE TRIGGER IF NOT EXISTS {tabelle}_weg AFTER DELETE ON {tabelle}
        BEGIN {markieren.format(z='OLD')} END;
        CREATE TRIGGER IF NOT EXISTS {tabelle}_anders AFTER UPDATE ON {tabelle} WHEN {anders}
        BEGIN {markieren.format(z='OLD')} {markieren.format(z='NEW')} END;
    '''


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


# --- Abgleich mit der Desktop-App (je Tag, siehe kern.tag_inhalt) ------------------------------------

def tage_stand(benutzer_id):
    """{datum: {'hash', 'geaendert'}} für alle Tage mit Inhalt oder bekannter Änderung (auch gelöschte)."""
    inhalte = kern.tage_gruppieren(eintraege(benutzer_id), bereitschaften(benutzer_id))
    zeiten = dict(db().execute('SELECT date, geaendert FROM tag_stand WHERE benutzer_id = ?', (benutzer_id,)))
    return {d: {'hash': kern.tag_hash(inhalte[d]) if d in inhalte else '', 'geaendert': zeiten.get(d, '')}
            for d in set(inhalte) | set(zeiten)}


def tage_inhalt(benutzer_id, daten):
    """{datum: {'inhalt', 'hash', 'geaendert'}} für die genannten Tage (leere Tage mit leerem Inhalt)."""
    daten = set(daten)
    inhalte = kern.tage_gruppieren([e for e in eintraege(benutzer_id) if e.date in daten],
                                   [b for b in bereitschaften(benutzer_id) if b.date in daten])
    zeiten = dict(db().execute('SELECT date, geaendert FROM tag_stand WHERE benutzer_id = ?', (benutzer_id,)))
    ergebnis = {}
    for d in daten:
        inhalt = inhalte.get(d, kern.tag_inhalt())
        ergebnis[d] = {'inhalt': inhalt, 'hash': kern.tag_hash(inhalt), 'geaendert': zeiten.get(d, '')}
    return ergebnis


def tag_ersetzen(benutzer_id, datum, inhalt, geaendert):
    """Ersetzt alle Einträge/Bereitschaften eines Tages durch `inhalt` (geprüft, kanonisch), ohne neu zu
    rechnen: die Minuten kommen so, wie die andere Seite sie gerechnet hat. Der Tag gilt danach als
    zum Zeitpunkt `geaendert` geändert (Änderungszeit der anderen Seite, wichtig für Konflikte)."""
    d = db()
    d.execute('DELETE FROM entries WHERE benutzer_id = ? AND date = ?', (benutzer_id, datum))
    d.execute('DELETE FROM bereitschaft_entries WHERE benutzer_id = ? AND date = ?', (benutzer_id, datum))
    for e in inhalt['eintraege']:
        eintrag_anlegen(benutzer_id, WorkEntry(None, datum, e['start'], e['end'], e['pause'], e['minutes'],
                                               e['reason'], e['target_minutes'], e['type']))
    for b in inhalt['bereitschaft']:
        bereitschaft_anlegen(benutzer_id, BereitschaftEntry(None, datum, b['start'], b['end'], b['note'],
                                                            b['end_date']))
    d.execute('INSERT OR REPLACE INTO tag_stand (benutzer_id, date, geaendert) VALUES (?, ?, ?)',
              (benutzer_id, datum, geaendert))


# --- Anwesenheit (Anmeldezeiten des Rechners, von der Desktop-App gemeldet) -------------------------

def anwesenheit(benutzer_id):
    """Alle Tage, neueste zuerst: [{'date', 'start', 'end'}] wie DBManager.load_all_device_logins."""
    zeilen = db().execute('SELECT date, start_time, end_time FROM anwesenheit WHERE benutzer_id = ? '
                          'ORDER BY date DESC', (benutzer_id,)).fetchall()
    return [{'date': z[0], 'start': z[1], 'end': z[2]} for z in zeilen]


def anwesenheit_tag(benutzer_id, datum):
    z = db().execute('SELECT start_time, end_time FROM anwesenheit WHERE benutzer_id = ? AND date = ?',
                     (benutzer_id, datum)).fetchone()
    return {'date': datum, 'start': z[0], 'end': z[1]} if z else None


def anwesenheit_melden(benutzer_id, datum, login, logout):
    """Zusammenführen wie in der Desktop-App: frühester Login und spätester Logout des Tages gewinnen
    (auch über mehrere Rechner). Leere Werte ändern nichts. HH:MM-Texte lassen sich direkt vergleichen."""
    db().execute(
        "INSERT INTO anwesenheit (benutzer_id, date, start_time, end_time) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(benutzer_id, date) DO UPDATE SET "
        "start_time = CASE WHEN excluded.start_time = '' THEN start_time WHEN start_time = '' "
        "  OR excluded.start_time < start_time THEN excluded.start_time ELSE start_time END, "
        "end_time = CASE WHEN excluded.end_time = '' THEN end_time WHEN end_time = '' "
        "  OR excluded.end_time > end_time THEN excluded.end_time ELSE end_time END",
        (benutzer_id, datum, login or '', logout or ''))


# --- Geräte: Zugang der Desktop-App (Token nur einmal angezeigt, gespeichert wird der SHA-256) -----

def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def geraet_anlegen(benutzer_id, name):
    token = 'uz_' + secrets.token_urlsafe(32)
    db().execute('INSERT INTO geraete (benutzer_id, name, token_hash) VALUES (?, ?, ?)',
                 (benutzer_id, name, _hash(token)))
    return token


def geraete(benutzer_id):
    return [dict(z) for z in db().execute('SELECT id, name, erstellt, zuletzt FROM geraete WHERE benutzer_id = ? '
                                          'ORDER BY id', (benutzer_id,))]


def geraet_loeschen(benutzer_id, geraet_id):
    db().execute('DELETE FROM geraete WHERE id = ? AND benutzer_id = ?', (geraet_id, benutzer_id))


def geraet_pruefen(token):
    """Token -> Zeile (id, benutzer_id, name, benutzer) oder None; merkt sich den letzten Kontakt."""
    if not token or len(token) > 200:
        return None
    z = db().execute('SELECT g.id, g.benutzer_id, g.name, b.name AS benutzer FROM geraete g '
                     'JOIN benutzer b ON b.id = g.benutzer_id WHERE g.token_hash = ?', (_hash(token),)).fetchone()
    if z:
        db().execute("UPDATE geraete SET zuletzt = datetime('now', 'localtime') WHERE id = ?", (z['id'],))
    return z
