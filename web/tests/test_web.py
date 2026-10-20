"""Prüfungen der Server-Version. Aufruf (Repo-Wurzel):  python -m unittest discover -s web/tests -v

Authentik wird durch eine Attrappe ersetzt, die Prüfungen brauchen kein Netz. Die Gegenprobe mit der
Desktop-App (gleiche Minuten) steht in tests/test_kern.py der Desktop-Tests.
"""

import datetime as dt
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HIER), os.path.dirname(os.path.dirname(HIER))]
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('ERSTES_PASSWORT', 'geheim123')

import app as uz  # noqa: E402
import austausch  # noqa: E402
import speicher  # noqa: E402

JETZT = dt.datetime(2026, 10, 12, 9, 30)      # Montag


class FalschesOidc:
    OidcFehler = uz.oidc.OidcFehler

    def __init__(self):
        self.info = {}

    def anmelde_url(self, issuer, client_id, redirect_uri, sitzung):
        sitzung['oidc'] = {'state': 's'}
        return 'https://auth.example/authorize'

    def rueckkehr(self, *args):
        return self.info


class Grundlage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.oidc = FalschesOidc()
        self.app = uz.erstelle_app({'DATENBANK': os.path.join(self.tmp.name, 't.db'), 'TESTING': True,
                                    'JETZT': JETZT, 'OIDC_ISSUER': 'https://auth.example/', 'OIDC_CLIENT_ID': 'id',
                                    'OIDC_CLIENT_SECRET': 'geheim', 'OIDC_GRUPPE': 'Überzeit',
                                    'OIDC_MODUL': self.oidc})
        self.c = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def anmelden(self, name='admin', passwort='geheim123'):
        tok = re.search(r'name="_csrf" value="([^"]+)"', self.c.get('/anmelden').text).group(1)
        r = self.c.post('/anmelden', data={'_csrf': tok, 'name': name, 'passwort': passwort})
        self.assertEqual(r.status_code, 302)
        self.tok = re.search(r'data-csrf="([^"]+)"', self.c.get('/').text).group(1)

    def post(self, pfad, **daten):
        return self.c.post(pfad, data=dict(daten, _csrf=self.tok))

    def meldungen(self):
        return re.findall(r'class="meldung (\w+)"[^>]*>([^<]+)', self.c.get('/').text)

    def eintraege(self, benutzer_id=1):
        with self.app.app_context():
            return speicher.eintraege(benutzer_id)


class AnmeldungTest(Grundlage):
    def test_ohne_anmeldung_umgeleitet(self):
        r = self.c.get('/kalender')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/anmelden', r.location)
        self.assertEqual(self.c.post('/api/vorschau', json={}).status_code, 400)   # ohne CSRF schon abgewiesen

    def test_falsches_passwort(self):
        tok = re.search(r'name="_csrf" value="([^"]+)"', self.c.get('/anmelden').text).group(1)
        r = self.c.post('/anmelden', data={'_csrf': tok, 'name': 'admin', 'passwort': 'falsch'})
        self.assertIn('stimmt nicht', r.text)

    def test_authentik_nur_mit_gruppe_und_je_person_eigene_daten(self):
        self.oidc.info = {'sub': 'a1', 'preferred_username': 'rebecca', 'groups': ['Andere']}
        self.c.get('/anmelden/authentik')
        r = self.c.get('/anmelden/authentik/zurueck?code=x&state=s')
        self.assertIn('/anmelden', r.location)
        self.oidc.info['groups'] = ['überzeit']                 # Groß-/Kleinschreibung egal
        self.c.get('/anmelden/authentik')
        r = self.c.get('/anmelden/authentik/zurueck?code=x&state=s')
        self.assertEqual(r.location, '/')
        self.tok = re.search(r'data-csrf="([^"]+)"', self.c.get('/').text).group(1)
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00')
        self.assertEqual(len(self.eintraege(2)), 1)
        self.assertEqual(self.eintraege(1), [])                # admin sieht nichts davon
        # fremden Eintrag weder sehen noch löschen
        self.c.post('/abmelden', data={'_csrf': self.tok})
        self.anmelden()
        self.assertEqual(self.c.get(f'/eintrag/{self.eintraege(2)[0].id}').status_code, 404)
        self.assertEqual(self.post('/loeschen', ids=str(self.eintraege(2)[0].id)).status_code, 404)
        self.assertEqual(len(self.eintraege(2)), 1)

    def test_offener_redirect_abgewiesen(self):
        tok = re.search(r'name="_csrf" value="([^"]+)"', self.c.get('/anmelden').text).group(1)
        r = self.c.post('/anmelden?weiter=//boese.example', data={'_csrf': tok, 'name': 'admin', 'passwort': 'geheim123'})
        self.assertEqual(r.location, '/')


class EintragenTest(Grundlage):
    def setUp(self):
        super().setUp()
        self.anmelden()

    def test_arbeit_mit_automatischer_pause(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00', anlass='Test')
        e, = self.eintraege()
        self.assertEqual((e.pause, e.minutes, e.reason), (30, 30, 'Test'))
        self.assertIn('+30m', self.meldungen()[0][1])

    def test_formular_startzustand_vom_server(self):
        """Was app.js sonst nach dem Laden aus- und einblendet, schickt schon der Server richtig (kein Springen)."""
        import re
        html = self.c.get('/').text
        versteckt = lambda attr: re.search(attr + r' class="[^"]*versteckt', html) is not None  # noqa: E731
        self.assertTrue(versteckt('data-nur="abwesend"'), 'bis-Feld sichtbar')
        self.assertTrue(versteckt('data-soll'), 'Soll-Feld sichtbar')
        self.assertTrue(versteckt('data-nur="korrektur"'), 'Korrektur sichtbar')
        self.assertFalse(versteckt('data-nur="zeiten"'))
        self.assertIn('Tag-Saldo <span class="gross zahl', html)          # Vorschau schon gerechnet
        self.assertNotIn('Berechne …', html)
        self.assertRegex(html, r'id="pause" name="pause"[^>]*value="30"')
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00')
        e, = self.eintraege()
        html = self.c.get(f'/eintrag/{e.id}').text
        self.assertIn('Netto 8h 30m', html)

    def test_zweiter_block_und_ueberschneidung(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='12:00')
        self.post('/eintragen', art='work', datum='2026-10-12', start='11:00', ende='13:00')
        self.assertEqual(self.meldungen()[-1][0], 'fehler')
        self.post('/eintragen', art='work', datum='2026-10-12', start='12:30', ende='16:00')
        erster, zweiter = sorted(self.eintraege(), key=lambda e: e.start)
        # 30 min Lücke zählt als Pause: keine weitere Pause, Überstunden am letzten Block
        self.assertEqual((erster.pause, erster.minutes, zweiter.pause, zweiter.minutes), (0, 0, 0, 30))

    def test_abwesenheit_ueberspringt_wochenende(self):
        self.post('/eintragen', art='vacation', datum='2026-10-15', bis='2026-10-20')
        self.assertEqual([e.date for e in sorted(self.eintraege(), key=lambda e: e.date)],
                         ['2026-10-15', '2026-10-16', '2026-10-19', '2026-10-20'])
        self.assertNotIn('Tage übrig', self.c.get('/').text)   # Urlaubskonto seit 1.7.0 weg
        ids = ','.join(str(e.id) for e in sorted(self.eintraege(), key=lambda e: e.date))
        self.assertIn(f'ids={ids}&', self.c.get('/eintraege?monat=2026-10').text.replace('&amp;', '&'))   # ein Block
        self.post('/abwesenheit', ids=ids, art='sick', von='2026-10-15', bis='2026-10-16')
        self.assertEqual(sorted((e.date, e.entry_type) for e in self.eintraege()),
                         [('2026-10-15', 'sick'), ('2026-10-16', 'sick')])

    def test_kalendertag_zeigt_ganze_zeitspanne(self):
        # Wunsch 20.10.2026: ein Tag aus einer mehrtägigen Abwesenheit zeigt im Kalender die ganze Zeitspanne
        self.post('/eintragen', art='parental', datum='2026-10-05', bis='2026-10-16')
        self.post('/eintragen', art='work', datum='2026-10-20', start='08:00', ende='16:30')
        ids = ','.join(str(e.id) for e in sorted(self.eintraege(), key=lambda e: e.date) if e.entry_type == 'parental')
        text = self.c.get('/kalender?monat=2026-10&tag=2026-10-08').text.replace('&amp;', '&')
        tag = text[text.index('id="tag"'):]
        self.assertIn('Elternzeit · 10 Tage', tag)
        self.assertIn(f'/abwesenheit?ids={ids}&', tag)                    # Bearbeiten für den ganzen Block
        self.assertIn('05.10. – 16.10.2026', tag)
        einzel = self.c.get('/kalender?monat=2026-10&tag=2026-10-20').text
        self.assertIn('08:00–16:30', einzel[einzel.index('id="tag"'):])   # Arbeitstag wie bisher

    def test_gleitzeitabbau_und_korrektur(self):
        self.post('/eintragen', art='flextime', datum='2026-10-13')
        self.post('/eintragen', art='work', korrektur='1', datum='2026-10-01', minuten='-1:30', anlass='Arzt')
        self.post('/eintragen', art='work', korrektur='1', datum='2026-10-02', minuten='1,5')
        self.assertEqual(sorted(e.minutes for e in self.eintraege()), [-480, -90, 90])

    def test_feiertag_ohne_soll(self):
        self.post('/eintragen', art='work', datum='2026-10-03', start='08:00', ende='10:00')   # Tag der Einheit
        self.assertEqual(self.eintraege()[0].minutes, 120)

    def test_eigenes_tagessoll(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='08:00', ende='12:00', eigenes_soll='1',
                  soll='04:00')
        e, = self.eintraege()
        self.assertEqual((e.target_minutes, e.minutes), (240, 0))

    def test_bearbeiten_rechnet_tag_neu_und_loeschen(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00')
        e, = self.eintraege()
        self.assertEqual(self.c.get(f'/eintrag/{e.id}').status_code, 200)
        self.post(f'/eintrag/{e.id}', art='work', datum='2026-10-12', start='07:00', ende='17:00')
        self.assertEqual(self.eintraege()[0].minutes, 75)      # netto über 9 h -> 45 min Pause
        self.post(f'/eintrag/{e.id}', art='work', datum='2026-10-12', start='06:00', ende='17:00')   # nur sich selbst
        self.assertEqual(self.eintraege()[0].minutes, 120)     # 11 h - 45 min = 10:15, gekappt auf 10 h
        self.post('/loeschen', ids=str(e.id))
        self.assertEqual(self.eintraege(), [])

    def test_vorschau(self):
        r = self.c.post('/api/vorschau', json={'datum': '2026-10-12', 'start': '07:00', 'ende_vorschlagen': True},
                        headers={'X-CSRF': self.tok})
        self.assertEqual((r.json['ende_vorschlag'], r.json['pause'], r.json['tag_saldo']), ('15:30', 30, 0))
        r = self.c.post('/api/vorschau', json={'datum': '2026-10-12', 'start': '07:00', 'ende': '21:00'},
                        headers={'X-CSRF': self.tok})
        self.assertIn('Maximum von 10 h erreicht', r.json['warnungen'])
        self.post('/eintragen', art='work', datum='2026-10-11', start='14:00', ende='23:00')
        r = self.c.post('/api/vorschau', json={'datum': '2026-10-12', 'start': '07:00', 'ende': '15:30'},
                        headers={'X-CSRF': self.tok})
        self.assertTrue(any('Ruhezeit' in w for w in r.json['warnungen']))
        r = self.c.post('/api/vorschau', json={'datum': '2026-10-11', 'start': '20:00', 'ende': '22:00'},
                        headers={'X-CSRF': self.tok})
        self.assertIn('ueberschneidung', r.json)

    def test_kommen_und_gehen(self):
        self.post('/stempeln/kommen', start='07:12')
        self.assertIn('Bei der Arbeit seit 07:12', self.c.get('/').text)
        self.post('/stempeln/gehen', ende='15:50')
        e, = self.eintraege()
        self.assertEqual((e.start, e.end, e.pause, e.minutes), ('07:12', '15:50', 30, 8))
        self.assertNotIn('Bei der Arbeit seit', self.c.get('/').text)
        self.post('/stempeln/kommen', start='16:00')                   # Soll schon erfüllt
        self.assertIn('Tagessoll ist heute schon erfüllt', self.c.get('/').text)

    def test_einstellungen_rechnen_alles_neu(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00')
        felder = {f'tag_{i}': '1' for i in range(5)}
        felder.update({f'soll_{i}': '07:00' for i in range(7)})
        self.post('/einstellungen', auto_break='1', default_start='07:00', max_work_hours='10',
                  vacation_entitlement='30', country='DE', state='TH', theme='dark', **felder,
                  br_nach=['06:00', '09:00'], br_pause=['30', '45'])
        self.assertEqual(self.eintraege()[0].minutes, 90)
        self.assertIn('data-wahl="dark"', self.c.get('/').text)

    def test_ziel(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='17:00')
        self.post('/ziel', aktiv='1', von='2026-12-21', bis='2026-12-23', stunden_berechnen='1')
        with self.app.app_context():
            w = speicher.einstellungen(1)
        self.assertEqual(w['goal_hours'], 24)
        self.assertIn('Minuten</b> länger', self.c.get('/ziel').text)

    def test_alle_seiten(self):
        self.post('/eintragen', art='work', datum='2026-10-12', start='07:00', ende='16:00')
        self.post('/bereitschaft', von='2026-10-12', bis='2026-10-14', notiz='Rufdienst')
        for pfad in ('/', '/eintraege', '/eintraege?monat=alle', '/kalender', '/kalender?monat=2026-10&tag=2026-10-13',
                     '/statistik', '/statistik?jahr=alle', '/ziel', '/bereitschaft', '/mehr', '/einstellungen',
                     '/austausch', '/manifest.webmanifest', '/sw.js', '/version', '/?datum=2026-10-14'):
            r = self.c.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            self.assertIn("default-src 'self'", r.headers['Content-Security-Policy'])
        self.assertIn('Rufdienst', self.c.get('/kalender?monat=2026-10&tag=2026-10-13').text)


class AustauschTest(Grundlage):
    def setUp(self):
        super().setUp()
        self.anmelden()

    def desktop_db(self, alt=False):
        pfad = os.path.join(self.tmp.name, 'ueberstunden_daten.db')
        if os.path.exists(pfad):
            os.remove(pfad)
        v = sqlite3.connect(pfad)
        if alt:     # Desktop-Stand vor Schema 1: ohne target_minutes/type, ohne Bereitschaft
            v.execute('CREATE TABLE entries (id INTEGER PRIMARY KEY, date TEXT, start TEXT, end TEXT, pause INTEGER, '
                      'minutes INTEGER, reason TEXT)')
        else:
            v.executescript('''CREATE TABLE entries (id INTEGER PRIMARY KEY, date TEXT, start TEXT, end TEXT,
                pause INTEGER, minutes INTEGER, reason TEXT, target_minutes INTEGER DEFAULT -1, type TEXT DEFAULT 'work');
                CREATE TABLE bereitschaft_entries (id INTEGER PRIMARY KEY, date TEXT, start TEXT, end TEXT, note TEXT,
                end_date TEXT);
                INSERT INTO bereitschaft_entries (date, start, end, note, end_date) VALUES ('2026-09-01', '', '', 'B', '');
                INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes, type)
                  VALUES ('2026-09-02', '', '', 0, 0, '', -1, 'vacation');''')
        v.execute("INSERT INTO entries (date, start, end, pause, minutes, reason) VALUES "
                  "('2026-09-01', '07:00', '16:00', 30, 30, 'alt')")
        v.commit()
        v.close()
        with open(pfad, 'rb') as f:
            return f.read()

    def hochladen(self, **dateien):
        daten = {k: (io.BytesIO(v), k) for k, v in dateien.items() if k in ('datenbank', 'einstellungen')}
        daten.update({k: v for k, v in dateien.items() if k not in ('datenbank', 'einstellungen')}, _csrf=self.tok)
        return self.c.post('/austausch', data=daten, content_type='multipart/form-data')

    def test_einlesen_ersetzen_und_exportieren(self):
        self.hochladen(datenbank=self.desktop_db())
        self.assertEqual(sorted((e.date, e.entry_type, e.minutes) for e in self.eintraege()),
                         [('2026-09-01', 'work', 30), ('2026-09-02', 'vacation', 0)])
        # zweites Mal nur mit Häkchen
        self.hochladen(datenbank=self.desktop_db())
        self.assertIn('Häkchen', self.c.get('/austausch').text)
        self.hochladen(datenbank=self.desktop_db(), ersetzen='1')
        self.assertEqual(len(self.eintraege()), 2)
        # Export im Desktop-Format
        roh = self.c.get('/export/datenbank').data
        pfad = os.path.join(self.tmp.name, 'zurueck.db')
        with open(pfad, 'wb') as f:
            f.write(roh)
        v = sqlite3.connect(pfad)
        self.assertEqual(v.execute('PRAGMA user_version').fetchone()[0], 3)
        self.assertEqual(v.execute('SELECT COUNT(*) FROM entries').fetchone()[0], 2)
        self.assertEqual(v.execute('SELECT note FROM bereitschaft_entries').fetchone()[0], 'B')
        v.close()
        csv_text = self.c.get('/export/csv').data.decode('utf-8-sig')
        self.assertTrue(csv_text.startswith('Datum;Zeitraum;Minuten;Dauer;Anlass'))
        self.assertIn('01.09.26;07:00 - 16:00 (-30m);30;30m;alt', csv_text)

    def test_alte_desktop_db(self):
        self.hochladen(datenbank=self.desktop_db(alt=True))
        e, = self.eintraege()
        self.assertEqual((e.entry_type, e.target_minutes, e.minutes), ('work', -1, 30))

    def test_einstellungen_rechnen_neu_und_werden_geprueft(self):
        self.hochladen(datenbank=self.desktop_db(alt=True))
        einst = {'weekday_targets': ['07:00'] * 5 + ['', ''], 'workdays': [0, 1, 2, 3, 4], 'db_path': '/geheim',
                 'max_work_hours': 'viel', 'state': 'BY', 'special_days': [{'day': 99, 'month': 1, 'target': '04:00'}]}
        self.hochladen(einstellungen=json.dumps(einst).encode())
        with self.app.app_context():
            w = speicher.einstellungen(1)
        self.assertNotIn('db_path', w)
        self.assertEqual((w['state'], w['max_work_hours'], w['special_days']), ('BY', 10, []))
        self.assertEqual(self.eintraege()[0].minutes, 90)       # 8h30 netto gegen 7h Soll

    def test_keine_datenbank(self):
        self.hochladen(datenbank=b'kein sqlite')
        self.assertIn('keine Datenbank der Desktop-App', self.c.get('/austausch').text)
        with self.assertRaises(austausch.AustauschFehler):
            austausch.desktop_einstellungen_lesen(b'[1, 2]', speicher.UEBERNEHMEN)


class AnwesenheitTest(Grundlage):
    """Die Desktop-App meldet Anmeldezeiten des Rechners mit einem Gerätezugang (Bearer, ohne Cookie)."""

    def setUp(self):
        super().setUp()
        self.anmelden()
        r = self.post('/anwesenheit', aktion='neu', name='Büro-PC')
        self.token = re.search(r'value="(uz_[^"]+)"', r.text).group(1)
        self.geraet = self.app.test_client()          # eigener Client: keine Sitzung, kein CSRF

    def melden(self, tage, token=None):
        return self.geraet.post('/api/geraet/anwesenheit', json={'tage': tage},
                                headers={'Authorization': f'Bearer {token or self.token}'})

    def test_zugang_pruefen_und_entfernen(self):
        r = self.geraet.get('/api/geraet/pruefen', headers={'Authorization': f'Bearer {self.token}'})
        self.assertEqual((r.status_code, r.json['benutzer'], r.json['geraet']), (200, 'admin', 'Büro-PC'))
        self.assertEqual(self.melden([], token='uz_falsch').status_code, 401)
        self.assertEqual(self.geraet.post('/api/geraet/anwesenheit', json={'tage': []}).status_code, 401)
        with self.app.app_context():
            self.assertNotIn(self.token, str([tuple(z) for z in speicher.db().execute('SELECT * FROM geraete')]))
            gid = speicher.geraete(1)[0]['id']
        self.assertIn('Büro-PC', self.c.get('/anwesenheit').text)
        self.post('/anwesenheit', aktion='entfernen', id=str(gid))
        self.assertEqual(self.melden([]).status_code, 401)

    def test_melden_zusammenfuehren_und_nutzen(self):
        r = self.melden([{'date': '2026-10-12', 'login': '07:12', 'logout': '12:00'},
                         {'date': '2026-10-09', 'login': '08:00', 'logout': ''},
                         {'date': 'kaputt', 'login': '07:00'}, {'date': '2026-10-08', 'login': '7:00'}, 'Unsinn'])
        self.assertEqual(r.json['tage'], 2)
        # zweiter Rechner: späterer Login ändert nichts, späterer Logout gewinnt
        self.melden([{'date': '2026-10-12', 'login': '07:40', 'logout': '16:03'}])
        with self.app.app_context():
            self.assertEqual(speicher.anwesenheit_tag(1, '2026-10-12'), {'date': '2026-10-12', 'start': '07:12',
                                                                          'end': '16:03'})
        seite = self.c.get('/anwesenheit').text
        self.assertIn('8h 51m', seite)
        heute = self.c.get('/').text
        self.assertIn('Kommen um 07:12', heute)
        self.assertIn('name="start" value="07:12"', heute)          # Startvorschlag im Formular
        self.post('/einstellungen', default_start='06:30', max_work_hours='10', vacation_entitlement='30',
                  country='DE', state='TH', theme='auto', tag_0='1', soll_0='08:00')
        self.assertNotIn('Kommen um', self.c.get('/').text)          # Haken aus -> wie am Desktop die Startzeit
        self.assertIn('name="start" value="06:30"', self.c.get('/').text)
        self.assertEqual(self.melden([{}] * 401).status_code, 400)

    def test_austausch_mit_desktop(self):
        pfad = os.path.join(self.tmp.name, 'd.db')
        v = sqlite3.connect(pfad)
        v.executescript("""CREATE TABLE entries (id INTEGER PRIMARY KEY, date TEXT, start TEXT, end TEXT, pause INTEGER,
            minutes INTEGER, reason TEXT); CREATE TABLE device_login (date TEXT PRIMARY KEY, start_time TEXT NOT NULL,
            end_time TEXT); INSERT INTO device_login VALUES ('2026-10-01', '06:58', '15:30'), ('2026-10-02', '', '');""")
        v.commit()
        v.close()
        with open(pfad, 'rb') as f:
            self.c.post('/austausch', data={'datenbank': (io.BytesIO(f.read()), 'd.db'), '_csrf': self.tok},
                        content_type='multipart/form-data')
        self.assertIn('1 Tage Anwesenheit', self.meldungen()[0][1])
        roh = self.c.get('/export/datenbank').data
        with open(pfad, 'wb') as f:
            f.write(roh)
        v = sqlite3.connect(pfad)
        self.assertEqual(v.execute('SELECT * FROM device_login').fetchall(), [('2026-10-01', '06:58', '15:30')])
        v.close()


if __name__ == '__main__':
    unittest.main()
