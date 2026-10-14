"""Browser-Tests: was nur im Browser passiert -- eigene Uhr (uhr.js), Live-Rechnung (app.js), Größen am Handy.

test_web.py sieht nur, was der Server schickt. Ob die Uhr statt der Android-Systemuhr aufgeht, die Live-Rechnung auf
die Uhr reagiert und am Handy nichts über den Rand ragt, zeigt nur ein echter Browser. Die App läuft dafür auf einem
freien Port und wird mit Chromium (Playwright) bedient. Ohne Playwright werden die Tests übersprungen (auch im
Docker-Image); UEBERZEIT_BROWSER=0 schaltet sie ab.
    venv/bin/pip install -r web/requirements-dev.txt && venv/bin/playwright install chromium
"""

import datetime as dt
import logging
import os
import re
import sys
import tempfile
import threading
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HIER), os.path.dirname(os.path.dirname(HIER))]
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('ERSTES_PASSWORT', 'geheim123')

import app as uz  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

AN = sync_playwright is not None and os.environ.get('UEBERZEIT_BROWSER', '1') != '0'
logging.getLogger('werkzeug').setLevel(logging.ERROR)
HANDY = {'width': 390, 'height': 844}


@unittest.skipUnless(AN, 'Playwright fehlt (pip install -r web/requirements-dev.txt)')
class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from werkzeug.serving import make_server
        cls.tmp = tempfile.TemporaryDirectory()
        anwendung = uz.erstelle_app({'DATENBANK': os.path.join(cls.tmp.name, 't.db'), 'TESTING': True,
                                     'JETZT': dt.datetime(2026, 10, 12, 9, 30)})
        cls.srv = make_server('127.0.0.1', 0, anwendung, threaded=True)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.srv.server_port}'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport=HANDY, has_touch=True, is_mobile=True)
        self.seite = self.ctx.new_page()
        self.fehler = []
        self.seite.on('pageerror', lambda e: self.fehler.append(str(e)))
        self.seite.goto(self.url + '/anmelden')
        self.seite.fill('#name', 'admin')
        self.seite.fill('#passwort', 'geheim123')
        self.seite.click('button[type=submit]')
        self.seite.wait_for_url(re.compile(r'.*/$'))

    def tearDown(self):
        self.ctx.close()
        self.assertEqual(self.fehler, [], 'JavaScript-Fehler auf der Seite')

    def uhr_tippen(self, knopf, stunde, minute):
        """Uhr über den Knopf öffnen, per Tastatur-Modus eine Zeit setzen, OK."""
        self.seite.click(knopf)
        blatt = self.seite.locator('dialog.uhr-blatt')
        blatt.wait_for(state='visible')
        self.seite.click('#uhr-tastatur')
        self.seite.fill('#uhr-std', stunde)
        self.seite.fill('#uhr-min', minute)
        self.seite.click('dialog.uhr-blatt button[value=ok]')
        blatt.wait_for(state='hidden')
        # das close-Ereignis des Dialogs kommt erst danach (eigene Aufgabe): warten, bis der Knopf die Zeit zeigt
        self.seite.wait_for_function('([k, w]) => document.querySelector(k).textContent === w',
                                     arg=[knopf, f'{stunde}:{minute}'])

    def test_keine_systemuhr_und_live_rechnung(self):
        s = self.seite
        self.assertEqual(s.locator('input[type=time]').count(), 0, 'noch ein natives Uhrzeitfeld')
        self.assertTrue(s.locator('#start-knopf').is_visible())
        self.uhr_tippen('#start-knopf', '08', '15')
        self.assertEqual(s.input_value('#start'), '08:15')
        self.assertEqual(s.inner_text('#start-knopf'), '08:15')
        # Live-Rechnung reagiert auf die Uhr: Ende fürs Tagessoll wird vorgeschlagen und im Knopf angezeigt
        s.wait_for_function("() => document.querySelector('.vorschau').innerText.includes('Tag-Saldo')")
        ende = s.input_value('#ende')
        self.assertRegex(ende, r'^1[5-7]:\d\d$')
        self.assertEqual(s.inner_text('#ende-knopf'), ende)
        # „Jetzt“ zieht den Knopf mit
        s.click('button[data-jetzt=ende]')
        self.assertEqual(s.inner_text('#ende-knopf'), s.input_value('#ende'))
        # Eintragen mit der gewählten Zeit
        self.uhr_tippen('#ende-knopf', '16', '45')
        s.click('form.eintrag-form button[type=submit]')
        s.wait_for_selector('.meldung')
        self.assertIn('08:15 - 16:45', s.inner_text('.eintraege'))

    def test_uhr_passt_aufs_handy(self):
        s = self.seite
        s.click('#start-knopf')
        s.locator('dialog.uhr-blatt').wait_for(state='visible')
        box = s.locator('dialog.uhr-blatt').bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], HANDY['width'])
        ok = s.locator('dialog.uhr-blatt button[value=ok]').bounding_box()
        self.assertLessEqual(ok['y'] + ok['height'], HANDY['height'], 'OK ragt unten heraus')
        s.click('dialog.uhr-blatt button[value=abbrechen]')

    def test_eigenes_tagessoll_und_haekchen(self):
        s = self.seite
        self.assertFalse(s.locator('#soll-knopf').is_visible(), 'Soll-Feld sichtbar, obwohl nicht gewählt')
        haken = s.locator('input[name=eigenes_soll]')
        box = haken.bounding_box()
        self.assertLessEqual(max(box['width'], box['height']), 24, f'Häkchen zu groß: {box}')
        haken.check()
        self.assertTrue(s.locator('#soll-knopf').is_visible())
        self.uhr_tippen('#soll-knopf', '06', '00')
        self.assertEqual(s.input_value('#soll'), '06:00')

    def test_seiten_am_handy_ohne_ueberlauf_und_ohne_riesenhaekchen(self):
        s = self.seite
        for pfad in ('/', '/eintraege', '/kalender', '/statistik', '/ziel', '/mehr', '/einstellungen',
                     '/anwesenheit', '/bereitschaft', '/austausch'):
            s.goto(self.url + pfad)
            breite = s.evaluate('document.documentElement.scrollWidth')
            self.assertLessEqual(breite, HANDY['width'], f'{pfad}: Seite {breite} px breit')
            zu_gross = s.evaluate("""() => [...document.querySelectorAll('input[type=checkbox]')]
                .map(e => e.getBoundingClientRect()).filter(r => r.width > 24 || r.height > 24).length""")
            self.assertEqual(zu_gross, 0, f'{pfad}: Häkchen größer als 24 px')
            self.assertEqual(s.locator('input[type=time]').count(), 0, f'{pfad}: natives Uhrzeitfeld')

    def test_ohne_leert_optionale_zeit(self):
        s = self.seite
        s.goto(self.url + '/bereitschaft')
        self.uhr_tippen('#start-knopf', '18', '00')
        self.assertEqual(s.input_value('#start'), '18:00')
        s.click('#start-knopf')
        s.click('dialog.uhr-blatt button[value=ohne]')
        s.wait_for_function("() => document.querySelector('#start-knopf').textContent === '--:--'")
        self.assertEqual(s.input_value('#start'), '')
        self.assertEqual(s.inner_text('#start-knopf'), '--:--')


if __name__ == '__main__':
    unittest.main()
