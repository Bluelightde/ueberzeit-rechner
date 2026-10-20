"""Überzeit -- Server-Version des Überzeit-Rechners (Arbeitszeit, Pausen, Überstunden).

Läuft im Browser und als installierbare App auf dem Handy, jede Person mit eigenen Daten. Gerechnet wird mit
kern.py aus dem Repo, also auf die Minute wie in der Desktop-App; deren Datenbank lässt sich einlesen und wieder
ausgeben (austausch.py). Flask + SQLite, Anmeldung über Authentik wie die übrigen Werkzeuge im Homelab.

Aufbau: Konfiguration -> Anmeldung/Sicherheit -> Routen. Daten: speicher.py, Rechnen: auswertung.py.
"""

import datetime as dt
import json
import logging
import os
import re
import secrets
import sys
import time
import urllib.parse
from functools import wraps

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))       # kern.py und models.py liegen im Repo eine Ebene höher

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,  # noqa: E402
                   session, url_for)
from flask.sessions import SecureCookieSessionInterface  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

import kern  # noqa: E402
import auswertung as aw  # noqa: E402
import austausch  # noqa: E402
import oidc  # noqa: E402
import speicher  # noqa: E402
from models import BereitschaftEntry, WorkEntry  # noqa: E402
from speicher import db  # noqa: E402

VERSION = '1.8.1'
ABGLEICH_MAX_TAGE = 1000
ZEITSTEMPEL = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z')
log = logging.getLogger('ueberzeit')

ARTEN = [(kern.TYPE_WORK, 'Arbeit'), (kern.TYPE_VACATION, 'Urlaub'), (kern.TYPE_SICK, 'Krank'),
         (kern.TYPE_FLEXTIME, 'Gleitzeitabbau'), (kern.TYPE_HOLIDAY, 'Feiertag'), (kern.TYPE_PARENTAL, 'Elternzeit')]


# --- Konfiguration -----------------------------------------------------------

def _wahr(wert):
    return str(wert).strip().lower() in ('1', 'true', 'ja', 'yes', 'on')


def _liste(text):
    return [a.strip() for a in (text or '').split(',') if a.strip()]


class _Sitzungscookie(SecureCookieSessionInterface):
    """COOKIE_NUR_HTTPS=auto: `Secure` nur, wenn die Anfrage über HTTPS kam (hinter NPM an X-Forwarded-Proto
    erkannt). So geht der Notzugang direkt per http im LAN (wie Kugelzeit/Vorratsliste)."""

    def get_cookie_secure(self, app):
        if app.config.get('COOKIE_AUTO'):
            return request.is_secure
        return super().get_cookie_secure(app)


def erstelle_app(test_konfig=None):
    app = Flask(__name__)
    cookie = os.environ.get('COOKIE_NUR_HTTPS', '0').strip().lower()
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', ''),
        DATENBANK=os.environ.get('DATENBANK', os.path.join(HIER, 'daten', 'ueberzeit.db')),
        APP_URL=os.environ.get('APP_URL', '').rstrip('/'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=_wahr(cookie),
        COOKIE_AUTO=cookie == 'auto',
        PERMANENT_SESSION_LIFETIME=dt.timedelta(days=int(os.environ.get('ANGEMELDET_TAGE', '90'))),
        OIDC_ISSUER=os.environ.get('OIDC_ISSUER', '').strip(),
        OIDC_CLIENT_ID=os.environ.get('OIDC_CLIENT_ID', '').strip(),
        OIDC_CLIENT_SECRET=os.environ.get('OIDC_CLIENT_SECRET', '').strip(),
        OIDC_NAME=os.environ.get('OIDC_NAME', 'Authentik'),
        # 🔑 Nur Mitglieder dieser Authentik-Gruppe kommen hinein (nicht jedes Konto), jede Person mit eigenen Daten.
        OIDC_GRUPPE=os.environ.get('OIDC_GRUPPE', '').strip(),
        LOKALE_ANMELDUNG=os.environ.get('LOKALE_ANMELDUNG', 'intern').strip().lower(),
        PROXY_ADRESSEN=_liste(os.environ.get('PROXY_ADRESSEN', '')),
        OIDC_MODUL=oidc,
        ANMELDE_SPERRE=(10, 15 * 60),
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,          # Desktop-Datenbank zum Einlesen
        JETZT=None,                                   # Tests: feste Uhrzeit (datetime)
    )
    if test_konfig:
        app.config.update(test_konfig)
    if app.config['OIDC_ISSUER'] and not app.config['OIDC_GRUPPE']:
        log.warning('Authentik ist eingerichtet, aber OIDC_GRUPPE fehlt – niemand kommt über Authentik herein')
    app.session_interface = _Sitzungscookie()
    if _wahr(os.environ.get('HINTER_PROXY', '0')):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if not app.config['SECRET_KEY']:
        raise RuntimeError('SECRET_KEY fehlt. In .env setzen, siehe README.')

    os.makedirs(os.path.dirname(os.path.abspath(app.config['DATENBANK'])), exist_ok=True)
    with app.app_context():
        speicher.schema_anlegen()
        erster_start()
        speicher.schliessen()       # teardown_appcontext ist hier noch nicht eingetragen -- sonst bleibt die Verbindung offen
    for endung in ('', '-wal', '-shm'):
        try:
            os.chmod(app.config['DATENBANK'] + endung, 0o600)
        except OSError:
            pass

    app.teardown_appcontext(speicher.schliessen)
    app.after_request(_sicherheitskopf)
    app.before_request(_csrf_pruefen)
    app.context_processor(lambda: {
        'csrf_token': _csrf_token, 'benutzer': aktueller_benutzer(), 'version': VERSION, 'oidc_an': oidc_aktiv(),
        'oidc_name': app.config['OIDC_NAME'], 'lokal_an': lokal_erlaubt(), 'zeit': aw.zeit, 'arten': ARTEN,
        'art_name': kern.TYPE_LABELS, 'art_farbe': aw.TYP_FARBEN, 'art_symbol': aw.TYP_SYMBOLE,
        'datum_kurz': aw.datum_kurz, 'datum_lang': aw.datum_lang, 'thema': _thema(),
    })
    _routen(app)
    return app


def jetzt():
    from flask import current_app
    return current_app.config['JETZT'] or dt.datetime.now()


def heute():
    return jetzt().date()


def erster_start():
    """Beim allerersten Start: lokales Admin-Konto als Notzugang (Passwort EINMAL ins Protokoll)."""
    d = db()
    if d.execute('SELECT COUNT(*) FROM benutzer').fetchone()[0]:
        return
    name = os.environ.get('ERSTER_BENUTZER', 'admin')
    passwort = os.environ.get('ERSTES_PASSWORT') or secrets.token_urlsafe(12)
    d.execute('INSERT INTO benutzer (name, pw_hash, admin) VALUES (?, ?, 1)', (name, generate_password_hash(passwort)))
    d.commit()
    if not os.environ.get('ERSTES_PASSWORT'):
        print('=' * 60, '\nERSTER START -- Notzugang:', f'\n  Benutzer: {name}', f'\n  Passwort: {passwort}',
              '\nIn einem Passwortmanager ablegen.\n' + '=' * 60, flush=True)


# --- Anmeldung und Sicherheit ------------------------------------------------------

def oidc_aktiv():
    from flask import current_app
    c = current_app.config
    return bool(c['OIDC_ISSUER'] and c['OIDC_CLIENT_ID'] and c['OIDC_CLIENT_SECRET'])


def _direkte_adresse():
    return request.environ.get('werkzeug.proxy_fix.orig', {}).get('REMOTE_ADDR') or request.remote_addr


def ueber_proxy():
    from flask import current_app
    return _direkte_adresse() in current_app.config['PROXY_ADRESSEN']


def _client_adresse():
    return request.remote_addr if ueber_proxy() else _direkte_adresse()


def lokal_erlaubt():
    """Passwortformular: 'intern' = nur direkt im LAN (nicht über NPM), 'immer', 'nie'."""
    from flask import current_app
    modus = current_app.config['LOKALE_ANMELDUNG']
    if modus == 'intern':
        return not ueber_proxy()
    return modus in ('immer', '1', 'ja')


def aktueller_benutzer():
    if 'benutzer_id' not in session:
        return None
    if 'benutzer' not in g:
        zeile = db().execute('SELECT id, name, admin, sitzung FROM benutzer WHERE id = ?',
                             (session['benutzer_id'],)).fetchone()
        if zeile is not None and zeile['sitzung'] != session.get('sitzung', 0):
            zeile = None
        g.benutzer = zeile
    return g.benutzer


def bid():
    return aktueller_benutzer()['id']


def sitzung_beginnen(benutzer_id, **merkmale):
    session.clear()
    g.pop('benutzer', None)
    session['benutzer_id'] = benutzer_id
    session['sitzung'] = db().execute('SELECT sitzung FROM benutzer WHERE id = ?', (benutzer_id,)).fetchone()[0]
    session.update(merkmale)
    session.permanent = True


def anmeldung_noetig(funktion):
    @wraps(funktion)
    def huelle(*args, **kwargs):
        if aktueller_benutzer() is None:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify(fehler='abgemeldet', abgemeldet=True), 401
            return redirect(url_for('anmelden', weiter=request.full_path.rstrip('?')))
        return funktion(*args, **kwargs)
    return huelle


def oidc_gruppen(info):
    gruppen = info.get('groups') or []
    return {str(gr).casefold() for gr in gruppen} if isinstance(gruppen, list) else set()


def oidc_benutzer(info):
    """Konto zu einer Authentik-Identität. Es entscheidet NUR die Gruppe OIDC_GRUPPE, bei jeder Anmeldung;
    wer drin ist, bekommt beim ersten Mal ein eigenes, leeres Konto.
    Reihenfolge: schon verknüpft (oidc_sub) -> Konto gleichen Namens ohne Verknüpfung -> neu."""
    from flask import current_app
    d = db()
    sub = info['sub']
    name = (info.get('preferred_username') or info.get('nickname') or '').strip()[:60]
    gruppe = current_app.config.get('OIDC_GRUPPE', '')
    if not gruppe:
        log.warning('OIDC_GRUPPE fehlt – Anmeldung über Authentik abgelehnt')
        return None
    if gruppe.casefold() not in oidc_gruppen(info):
        log.warning('Authentik-Anmeldung abgelehnt: "%s" ist nicht in der Gruppe "%s"', name or sub, gruppe)
        return None
    zeile = d.execute('SELECT * FROM benutzer WHERE oidc_sub = ?', (sub,)).fetchone()
    if zeile is not None:
        return zeile['id']
    if not name:
        return None
    zeile = d.execute('SELECT * FROM benutzer WHERE name = ?', (name,)).fetchone()
    if zeile is not None and zeile['oidc_sub']:
        return None                     # Name schon mit anderer Authentik-Kennung verknüpft
    if zeile is not None:
        d.execute('UPDATE benutzer SET oidc_sub = ? WHERE id = ?', (sub, zeile['id']))
        benutzer_id = zeile['id']
    else:
        benutzer_id = d.execute("INSERT INTO benutzer (name, pw_hash, oidc_sub) VALUES (?, '!', ?)",
                                (name, sub)).lastrowid
    d.commit()
    return benutzer_id


def geraet_noetig(funktion):
    """Für die Desktop-App: Kopfzeile „Authorization: Bearer uz_…“. Falsche Zugänge zählen wie falsche Passwörter."""
    @wraps(funktion)
    def huelle(*args, **kwargs):
        if anmeldung_gesperrt():
            return jsonify(fehler='Zu viele Fehlversuche, bitte später noch einmal.'), 429
        art, _, token = request.headers.get('Authorization', '').partition(' ')
        geraet = speicher.geraet_pruefen(token.strip()) if art.lower() == 'bearer' else None
        if geraet is None:
            db().execute('INSERT INTO anmeldeversuche VALUES (?, ?)', (_client_adresse(), time.time()))
            db().commit()
            return jsonify(fehler='Gerätezugang unbekannt oder entfernt.'), 401
        g.geraet = geraet
        return funktion(*args, **kwargs)
    return huelle


def anmeldung_gesperrt():
    from flask import current_app
    grenze, fenster = current_app.config['ANMELDE_SPERRE']
    d = db()
    d.execute('DELETE FROM anmeldeversuche WHERE zeit < ?', (time.time() - fenster,))
    anzahl = d.execute('SELECT COUNT(*) FROM anmeldeversuche WHERE schluessel = ?', (_client_adresse(),)).fetchone()[0]
    d.commit()
    return anzahl >= grenze


def _csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(24)
    return session['_csrf']


def _csrf_pruefen():
    """Formulare schicken das Feld _csrf, die Live-Rechnung (JSON) die Kopfzeile X-CSRF.
    Ausnahme /api/geraet/: Die Desktop-App meldet sich mit ihrem Gerätezugang (Bearer), ohne Cookie."""
    if request.method == 'POST' and not request.path.startswith('/api/geraet/'):
        erwartet = session.get('_csrf')
        gesendet = request.headers.get('X-CSRF') or request.form.get('_csrf', '')
        if not erwartet or not secrets.compare_digest(erwartet, gesendet):
            if request.path.startswith('/api/'):
                abort(Response(json.dumps({'fehler': 'Sitzung abgelaufen – bitte die Seite neu laden.'}), 400,
                               mimetype='application/json'))
            abort(400, 'Formular abgelaufen. Bitte die Seite neu laden und noch einmal versuchen.')


def _sicheres_ziel(ziel):
    """Nur eigene Pfade (kein Open Redirect; Steuerzeichen und Backslash abgewiesen)."""
    ziel = (ziel or '').strip()
    if (not ziel.startswith('/') or ziel.startswith('//') or '\\' in ziel
            or any(ord(z) < 32 or ord(z) == 127 for z in ziel)):
        return url_for('heute_seite')
    teile = urllib.parse.urlsplit(ziel)
    return url_for('heute_seite') if teile.scheme or teile.netloc else ziel


CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
       "manifest-src 'self'; form-action 'self'")


def _sicherheitskopf(antwort):
    kopf = antwort.headers
    kopf.setdefault('Content-Security-Policy', CSP)
    kopf.setdefault('X-Content-Type-Options', 'nosniff')
    kopf.setdefault('X-Frame-Options', 'DENY')
    kopf.setdefault('Referrer-Policy', 'same-origin')
    kopf.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
    if request.path.startswith('/static/') and request.query_string and antwort.status_code == 200:
        antwort.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif not request.path.startswith('/static/'):
        antwort.headers.setdefault('Cache-Control', 'no-cache')
    if request.is_secure:
        kopf.setdefault('Strict-Transport-Security', 'max-age=15552000')
    return antwort


def _thema():
    b = aktueller_benutzer()
    if b is None:
        return 'auto'
    wert = werte().get('theme')
    return wert if wert in ('light', 'dark') else 'auto'


# --- Eingaben lesen -------------------------------------------------------------------

def _datum(text, standard=None):
    return kern.parse_date((text or '').strip()) or standard


def _uhrzeit(text):
    text = (text or '').strip()
    if re.fullmatch(r'\d:\d\d', text):
        text = '0' + text
    return text if kern.parse_hhmm(text) is not None else None


def _minuten(text):
    """'-1:30', '+45', '90', '1,5' (Stunden mit Komma) -> Minuten mit Vorzeichen, None wenn unlesbar."""
    text = (text or '').strip().replace(' ', '').replace('−', '-')
    m = re.fullmatch(r'([+-]?)(\d{1,3}):(\d{2})', text)
    if m:
        wert = int(m.group(2)) * 60 + int(m.group(3))
        return -wert if m.group(1) == '-' else wert
    m = re.fullmatch(r'([+-]?)(\d{1,3})[,.](\d{1,2})h?', text)
    if m:
        wert = round(float(f'{m.group(2)}.{m.group(3)}') * 60)
        return -wert if m.group(1) == '-' else wert
    m = re.fullmatch(r'([+-]?\d{1,5})(m|min)?', text)
    return int(m.group(1)) if m else None


def _ganzzahl(text, standard=0, unten=None, oben=None):
    try:
        wert = int(str(text).strip())
    except (TypeError, ValueError):
        return standard
    if unten is not None:
        wert = max(unten, wert)
    if oben is not None:
        wert = min(oben, wert)
    return wert


def werte():
    """Einstellungen der angemeldeten Person (pro Anfrage einmal gelesen)."""
    if 'werte' not in g:
        g.werte = speicher.einstellungen(bid())
    return g.werte


def alle():
    if 'alle' not in g:
        g.alle = speicher.eintraege(bid())
    return g.alle


def _neu_laden():
    g.pop('alle', None)
    return alle()


def _monatswahl():
    """Monatsfilter der Eintragstabelle: (vorhandene Monate, gewählter Monat oder 'alle')."""
    monate = sorted({e.date[:7] for e in alle() if len(e.date) >= 7}, reverse=True)
    monat = request.args.get('monat') or (monate[0] if monate else heute().isoformat()[:7])
    if monat != 'alle' and not re.fullmatch(r'\d{4}-\d{2}', monat):
        monat = heute().isoformat()[:7]
    return monate, monat


def _anmeldezeit(datum):
    """Anmeldezeit des Rechners an dem Tag (von der Desktop-App gemeldet), wenn sie genutzt werden soll."""
    if not werte().get('use_login_time', True):
        return None
    tag = speicher.anwesenheit_tag(bid(), datum)
    return tag['start'] if tag and tag['start'] else None


def _start_vorschlag(datum):
    """Beginn fürs Formular: Ende des letzten Eintrags an dem Tag, sonst die Anmeldezeit des Rechners
    (wie „Login-Zeit als Startzeit verwenden“ am Desktop), sonst die gewohnte Startzeit."""
    tag = [e for e in alle() if e.date == datum and e.end]
    if tag:
        return max(e.end for e in tag)
    return _anmeldezeit(datum) or werte().get('default_start', '07:00')


# --- Routen ----------------------------------------------------------------------------

def _routen(app):  # noqa: C901

    @app.get('/version')
    def version():
        try:
            db().execute('SELECT 1').fetchone()
            zustand = 'ok'
        except Exception:  # noqa: BLE001 -- jede Störung der Datenbank heißt "nicht gesund"
            zustand = 'fehler'
        return jsonify(version=VERSION, datenbank=zustand), (200 if zustand == 'ok' else 503)

    @app.get('/sw.js')
    def service_worker():
        js = render_template('sw.js', version=VERSION,
                             vorab=[url_for('static', filename=f) + f'?v={VERSION}'
                                    for f in ('css/app.css', 'js/app.js', 'js/thema.js', 'icons/icon.svg')]
                                   + [url_for('static', filename='vendor/bootstrap-icons/bootstrap-icons.min.css')],
                             nie=['/anmelden', '/abmelden', '/ueberall-abmelden', '/version', '/sw.js', '/api',
                                  '/export'])
        return app.response_class(js, mimetype='application/javascript', headers={'Cache-Control': 'no-cache'})

    @app.get('/manifest.webmanifest')
    def manifest():
        return app.response_class(json.dumps({
            'name': 'Überzeit', 'short_name': 'Überzeit', 'description': 'Arbeitszeit und Überstunden',
            'start_url': '/', 'scope': '/', 'display': 'standalone', 'lang': 'de',
            # Grundfarben wie die anderen Apps schwarz: Chrome färbt damit die Navigationsleiste beim Kaltstart
            'background_color': '#000000', 'theme_color': '#000000',
            'shortcuts': [{'name': 'Eintragen', 'url': '/#eintragen'}, {'name': 'Kalender', 'url': '/kalender'}],
            'icons': [{'src': url_for('static', filename='icons/icon-192.png') + f'?v={VERSION}', 'sizes': '192x192',
                       'type': 'image/png', 'purpose': 'any'},
                      {'src': url_for('static', filename='icons/icon-512.png') + f'?v={VERSION}', 'sizes': '512x512',
                       'type': 'image/png', 'purpose': 'any'},
                      {'src': url_for('static', filename='icons/maskable.svg') + f'?v={VERSION}', 'sizes': 'any',
                       'type': 'image/svg+xml', 'purpose': 'maskable'}],
        }, ensure_ascii=False), mimetype='application/manifest+json')

    # --- Anmeldung ---

    @app.route('/anmelden', methods=['GET', 'POST'])
    def anmelden():
        if request.method == 'POST':
            if not lokal_erlaubt():
                abort(403)
            if anmeldung_gesperrt():
                flash('Zu viele Fehlversuche. Bitte in 15 Minuten noch einmal versuchen.', 'fehler')
                return render_template('anmelden.html', weiter=request.args.get('weiter', '')), 429
            zeile = db().execute('SELECT * FROM benutzer WHERE name = ?',
                                 (request.form.get('name', '').strip(),)).fetchone()
            if (zeile and zeile['pw_hash'] != '!'
                    and check_password_hash(zeile['pw_hash'], request.form.get('passwort', ''))):
                sitzung_beginnen(zeile['id'])
                db().execute('DELETE FROM anmeldeversuche WHERE schluessel = ?', (_client_adresse(),))
                db().commit()
                return redirect(_sicheres_ziel(request.args.get('weiter')))
            db().execute('INSERT INTO anmeldeversuche VALUES (?, ?)', (_client_adresse(), time.time()))
            db().commit()
            log.warning('Fehlgeschlagene Anmeldung für "%s" von %s', request.form.get('name', '')[:60],
                        _client_adresse())
            flash('Benutzername oder Passwort stimmt nicht.', 'fehler')
        return render_template('anmelden.html', weiter=request.args.get('weiter', ''))

    def _rueck_url():
        return (app.config['APP_URL'] + '/anmelden/authentik/zurueck') if app.config['APP_URL'] \
            else url_for('oidc_zurueck', _external=True)

    @app.get('/anmelden/authentik')
    def oidc_start():
        if not oidc_aktiv():
            abort(404)
        try:
            ziel = app.config['OIDC_MODUL'].anmelde_url(app.config['OIDC_ISSUER'], app.config['OIDC_CLIENT_ID'],
                                                       _rueck_url(), session)
        except oidc.OidcFehler as e:
            flash(f'Anmeldung über {app.config["OIDC_NAME"]} geht gerade nicht: {e}', 'fehler')
            return redirect(url_for('anmelden'))
        session['oidc_weiter'] = _sicheres_ziel(request.args.get('weiter'))
        return redirect(ziel)

    @app.get('/anmelden/authentik/zurueck')
    def oidc_zurueck():
        if not oidc_aktiv():
            abort(404)
        weiter = session.get('oidc_weiter') or url_for('heute_seite')
        try:
            info = app.config['OIDC_MODUL'].rueckkehr(app.config['OIDC_ISSUER'], app.config['OIDC_CLIENT_ID'],
                                                      app.config['OIDC_CLIENT_SECRET'], _rueck_url(), session,
                                                      request.args)
        except oidc.OidcFehler as e:
            log.warning('OIDC-Anmeldung fehlgeschlagen: %s', e)
            flash(str(e), 'fehler')
            return redirect(url_for('anmelden'))
        benutzer_id = oidc_benutzer(info)
        if benutzer_id is None:
            flash('Für dieses Konto gibt es hier keinen Zugang.', 'fehler')
            return redirect(url_for('anmelden'))
        sitzung_beginnen(benutzer_id, per_oidc=True)
        return redirect(_sicheres_ziel(weiter))

    @app.post('/abmelden')
    def abmelden():
        session.clear()
        antwort = redirect(url_for('anmelden'))
        antwort.headers['Clear-Site-Data'] = '"cache", "storage"'      # Offline-Speicher auf dem Gerät löschen
        return antwort

    @app.post('/ueberall-abmelden')
    @anmeldung_noetig
    def ueberall_abmelden():
        db().execute('UPDATE benutzer SET sitzung = sitzung + 1 WHERE id = ?', (bid(),))
        db().commit()
        session.clear()
        flash('Auf allen Geräten abgemeldet.', 'ok')
        antwort = redirect(url_for('anmelden'))
        antwort.headers['Clear-Site-Data'] = '"cache", "storage"'
        return antwort

    # --- Heute ---

    @app.get('/')
    @anmeldung_noetig
    def heute_seite():
        h = heute()
        datum = h.isoformat()
        # „Für diesen Tag eintragen“ aus dem Kalender: Formular für das Datum vorbereiten
        form_datum = (_datum(request.args.get('datum')) or h).isoformat()
        start = _start_vorschlag(form_datum)
        laufend = werte().get('laufend')
        lauf = None
        if laufend:
            beginn = dt.datetime.fromisoformat(f'{laufend["datum"]}T{laufend["start"]}')
            vorschlag = aw.ende_vorschlag(alle(), werte(), laufend['datum'], laufend['start'])
            lauf = {'datum': laufend['datum'], 'start': laufend['start'], 'ende_soll': vorschlag,
                    'seit': int((jetzt() - beginn).total_seconds() // 60), 'beginn_ms': int(beginn.timestamp() * 1000)}
        heute_eintraege = sorted([e for e in alle() if e.date == datum], key=lambda e: e.start or '')
        monate, monat = _monatswahl()   # Tabelle darunter wie im Desktop-Reiter „Eingabe & Liste“
        ende = aw.ende_vorschlag(alle(), werte(), form_datum, start)
        return render_template(
            'heute.html', datum=datum, form_datum=form_datum, start=start, ende=ende,
            vorschau=aw.vorschau(alle(), werte(), form_datum, start, ende) if start and ende else None,
            saldo=aw.saldo(alle()), ziel=aw.ziel(alle(), werte(), h),
            soll=kern.get_target_minutes_for_date(datum, alle(), werte()), auto=werte().get('auto_break', True),
            heute_eintraege=heute_eintraege, tag_saldo=sum(e.minutes for e in heute_eintraege), lauf=lauf,
            bloecke=aw.bloecke(alle(), werte(), None if monat == 'alle' else monat), monate=monate, monat=monat,
            angemeldet=_anmeldezeit(datum),
            woche=aw.woche(alle(), werte(), h),
            monat_name=_monat_name, leer=not alle())

    @app.post('/api/vorschau')
    @anmeldung_noetig
    def api_vorschau():
        """Live-Rechnung fürs Formular: Pause, Überstunden, Netto, Warnungen und das Ende fürs Tagessoll."""
        d = request.get_json(silent=True) or {}
        datum = _datum(d.get('datum'))
        start = _uhrzeit(d.get('start'))
        if datum is None or start is None:
            return jsonify(fehler='Datum oder Beginn fehlt'), 400
        datum = datum.isoformat()
        soll = _uhrzeit(d.get('soll')) if d.get('soll') else None
        soll = kern.hhmm_to_minutes(soll) if soll else None
        ohne = _ganzzahl(d.get('ohne_id'), None)
        pause = _ganzzahl(d.get('pause'), 0, 0, 600)
        antwort = {'soll_tag': soll_fuer(datum, soll)}
        if d.get('ende_vorschlagen'):
            antwort['ende_vorschlag'] = aw.ende_vorschlag(alle(), werte(), datum, start, pause, soll, ohne)
        ende = _uhrzeit(d.get('ende')) or antwort.get('ende_vorschlag')
        if ende:
            antwort.update(aw.vorschau(alle(), werte(), datum, start, ende, pause, soll, ohne))
            antwort['ende'] = ende
        return jsonify(antwort)

    def soll_fuer(datum, eigenes):
        return aw.soll_fuer(datum, alle(), werte(), eigenes)

    def _gespeichert(text, ziel=None):
        flash(text, 'ok')
        return redirect(_sicheres_ziel(ziel or request.form.get('weiter') or url_for('heute_seite')))

    def _arbeit_speichern(datum, start, ende, pause, anlass, eigenes_soll, ohne_id=None):
        """Neuer oder geänderter Zeiteintrag: Überschneidung prüfen, rechnen, Tag neu verteilen.
        Gibt (eintrag, fehler) zurück."""
        v = aw.vorschau(alle(), werte(), datum, start, ende, pause, eigenes_soll, ohne_id)
        if 'ueberschneidung' in v:
            return None, f'Überschneidung mit {v["ueberschneidung"]}. Bitte die Zeiten korrigieren.'
        return WorkEntry(ohne_id, datum, start, ende, v['pause'], v['ueberstunden'], anlass,
                         -1 if eigenes_soll is None else eigenes_soll, kern.TYPE_WORK), None

    def _abwesenheit_anlegen(art, von, bis):
        """Ein Eintrag je Tag; bei mehreren Tagen werden freie Tage (Soll 0) übersprungen (wie die Desktop-App)."""
        bis = max(von, bis)
        tage, d = [], von
        while d <= bis:
            ds = d.isoformat()
            if von == bis or kern.get_target_minutes_for_date(ds, alle(), werte()) > 0:
                speicher.eintrag_anlegen(bid(), WorkEntry(None, ds, '', '', 0, 0, '', -1, art))
                tage.append(ds)
            d += dt.timedelta(days=1)
        return tage

    @app.post('/eintragen')
    @anmeldung_noetig
    def eintragen():
        f = request.form
        art = f.get('art', kern.TYPE_WORK)
        if art not in kern.ALL_TYPES:
            abort(400, 'Unbekannte Art.')
        datum = _datum(f.get('datum'))
        if datum is None:
            flash('Bitte ein gültiges Datum angeben.', 'fehler')
            return redirect(url_for('heute_seite') + '#eintragen')
        ds = datum.isoformat()
        if art == kern.TYPE_WORK and f.get('korrektur'):
            minuten = _minuten(f.get('minuten'))
            if minuten is None or minuten == 0:
                flash('Bitte die Korrektur in Minuten oder als Stunden:Minuten angeben, z. B. -0:30.', 'fehler')
                return redirect(url_for('heute_seite') + '#eintragen')
            speicher.eintrag_anlegen(bid(), WorkEntry(None, ds, '', '', 0, minuten, f.get('anlass', '').strip()[:200],
                                                      -1, kern.TYPE_WORK))
            db().commit()
            return _gespeichert(f'Korrektur {aw.zeit(minuten, True)} am {aw.datum_kurz(ds)} gespeichert.')
        if art == kern.TYPE_WORK:
            start, ende = _uhrzeit(f.get('start')), _uhrzeit(f.get('ende'))
            if start is None or ende is None:
                flash('Bitte Beginn und Ende als Uhrzeit angeben.', 'fehler')
                return redirect(url_for('heute_seite') + '#eintragen')
            soll = kern.hhmm_to_minutes(_uhrzeit(f.get('soll')) or '00:00') if f.get('eigenes_soll') else None
            e, fehler = _arbeit_speichern(ds, start, ende, _ganzzahl(f.get('pause'), 0, 0, 600),
                                          f.get('anlass', '').strip()[:200], soll)
            if fehler:
                flash(fehler, 'fehler')
                return redirect(url_for('heute_seite') + '#eintragen')
            speicher.eintrag_anlegen(bid(), e)
            speicher.tage_neu_berechnen(bid(), [ds], _neu_laden(), werte())
            db().commit()
            neu = speicher.eintrag(bid(), e.id)
            return _gespeichert(f'{aw.datum_kurz(ds)} {start}–{ende} gespeichert: {aw.zeit(neu.minutes, True)}.')
        bis = _datum(f.get('bis'), datum)
        tage = _abwesenheit_anlegen(art, datum, bis)
        if not tage:
            flash('Im gewählten Zeitraum liegt kein Arbeitstag.', 'fehler')
            return redirect(url_for('heute_seite') + '#eintragen')
        speicher.tage_neu_berechnen(bid(), tage, _neu_laden(), werte())
        db().commit()
        return _gespeichert(f'{kern.TYPE_LABELS[art]}: {len(tage)} Tag{"e" if len(tage) != 1 else ""} eingetragen.')

    # --- Kommen / Gehen ---

    @app.post('/stempeln/kommen')
    @anmeldung_noetig
    def kommen():
        w = werte()
        if not w.get('laufend'):
            jetzt_ = jetzt()
            start = _uhrzeit(request.form.get('start')) or jetzt_.strftime('%H:%M')
            w['laufend'] = {'datum': jetzt_.date().isoformat(), 'start': start}
            speicher.einstellungen_speichern(bid(), w)
            db().commit()
            flash(f'Arbeitsbeginn {start} gemerkt.', 'ok')
        return redirect(url_for('heute_seite'))

    @app.post('/stempeln/gehen')
    @anmeldung_noetig
    def gehen():
        w = werte()
        lauf = w.get('laufend')
        if not lauf:
            return redirect(url_for('heute_seite'))
        ende = _uhrzeit(request.form.get('ende')) or jetzt().strftime('%H:%M')
        e, fehler = _arbeit_speichern(lauf['datum'], lauf['start'], ende, 0, request.form.get('anlass', '').strip()[:200],
                                      None)
        if fehler:
            flash(fehler, 'fehler')
            return redirect(url_for('heute_seite'))
        speicher.eintrag_anlegen(bid(), e)
        speicher.tage_neu_berechnen(bid(), [lauf['datum']], _neu_laden(), w)
        w.pop('laufend', None)
        speicher.einstellungen_speichern(bid(), w)
        db().commit()
        neu = speicher.eintrag(bid(), e.id)
        return _gespeichert(f'Feierabend: {lauf["start"]}–{ende} gespeichert, {aw.zeit(neu.minutes, True)}.')

    @app.post('/stempeln/verwerfen')
    @anmeldung_noetig
    def verwerfen():
        w = werte()
        if w.pop('laufend', None):
            speicher.einstellungen_speichern(bid(), w)
            db().commit()
            flash('Arbeitsbeginn verworfen.', 'ok')
        return redirect(url_for('heute_seite'))

    # --- Einträge ---

    @app.get('/eintraege')
    @anmeldung_noetig
    def liste():
        monate, monat = _monatswahl()
        bl = aw.bloecke(alle(), werte(), None if monat == 'alle' else monat)
        return render_template('liste.html', bloecke=bl, monate=monate, monat=monat, saldo=aw.saldo(alle()),
                               summe=sum(b['minuten'] for b in bl), monat_name=_monat_name)

    def _eigene(ids_text):
        ids = [_ganzzahl(i, None) for i in (ids_text or '').split(',')]
        gefunden = [speicher.eintrag(bid(), i) for i in ids if i]
        if not gefunden or None in gefunden:
            abort(404)
        return sorted(gefunden, key=lambda e: e.date)

    @app.route('/eintrag/<int:eintrag_id>', methods=['GET', 'POST'])
    @anmeldung_noetig
    def bearbeiten(eintrag_id):
        e = speicher.eintrag(bid(), eintrag_id)
        if e is None:
            abort(404)
        if request.method == 'GET':
            vorschau = None
            if e.entry_type == kern.TYPE_WORK and e.start and e.end:
                vorschau = aw.vorschau(alle(), werte(), e.date, e.start, e.end, e.pause,
                                       e.target_minutes if e.target_minutes != -1 else None, e.id)
            return render_template('bearbeiten.html', e=e, weiter=request.args.get('weiter', ''),
                                   auto=werte().get('auto_break', True), vorschau=vorschau,
                                   soll_text=kern.minutes_to_hhmm(e.target_minutes) if e.target_minutes != -1 else '')
        f = request.form
        alt_datum = e.date
        art = f.get('art', e.entry_type)
        datum = _datum(f.get('datum'))
        if art not in kern.ALL_TYPES or datum is None:
            flash('Bitte Art und Datum prüfen.', 'fehler')
            return redirect(url_for('bearbeiten', eintrag_id=e.id))
        ds = datum.isoformat()
        soll = kern.hhmm_to_minutes(_uhrzeit(f.get('soll')) or '00:00') if (art == kern.TYPE_WORK
                                                                             and f.get('eigenes_soll')) else None
        if art == kern.TYPE_WORK and not f.get('korrektur'):
            start, ende = _uhrzeit(f.get('start')), _uhrzeit(f.get('ende'))
            if start is None or ende is None:
                flash('Bitte Beginn und Ende als Uhrzeit angeben.', 'fehler')
                return redirect(url_for('bearbeiten', eintrag_id=e.id))
            neu, fehler = _arbeit_speichern(ds, start, ende, _ganzzahl(f.get('pause'), 0, 0, 600),
                                            f.get('anlass', '').strip()[:200], soll, ohne_id=e.id)
            if fehler:
                flash(fehler, 'fehler')
                return redirect(url_for('bearbeiten', eintrag_id=e.id))
        elif art == kern.TYPE_WORK:
            minuten = _minuten(f.get('minuten'))
            if minuten is None:
                flash('Bitte die Minuten prüfen, z. B. -0:30 oder 45.', 'fehler')
                return redirect(url_for('bearbeiten', eintrag_id=e.id))
            neu = WorkEntry(e.id, ds, '', '', 0, minuten, f.get('anlass', '').strip()[:200],
                            -1 if soll is None else soll, art)
        else:
            neu = WorkEntry(e.id, ds, '', '', 0, 0, '', -1, art)
        speicher.eintrag_aendern(bid(), neu)
        speicher.tage_neu_berechnen(bid(), [alt_datum, ds], _neu_laden(), werte())
        db().commit()
        return _gespeichert(f'Eintrag vom {aw.datum_kurz(ds)} gespeichert.', f.get('weiter') or url_for('liste'))

    @app.post('/loeschen')
    @anmeldung_noetig
    def loeschen():
        block = _eigene(request.form.get('ids'))
        for e in block:
            speicher.eintrag_loeschen(bid(), e.id)
        speicher.tage_neu_berechnen(bid(), [e.date for e in block], _neu_laden(), werte())
        db().commit()
        text = (f'Eintrag vom {aw.datum_kurz(block[0].date)} gelöscht.' if len(block) == 1 else
                f'{len(block)} Tage ({aw.datum_kurz(block[0].date)} – {aw.datum_kurz(block[-1].date)}) gelöscht.')
        return _gespeichert(text, request.form.get('weiter') or url_for('liste'))

    @app.route('/abwesenheit', methods=['GET', 'POST'])
    @anmeldung_noetig
    def abwesenheit():
        """Mehrtägige Abwesenheit als Ganzes ändern: alte Tage ersetzen (wie AbsenceEditDialog)."""
        block = _eigene(request.values.get('ids'))
        if any(e.entry_type == kern.TYPE_WORK for e in block):
            abort(400, 'Arbeitszeiten bitte einzeln bearbeiten.')
        if request.method == 'GET':
            return render_template('abwesenheit.html', block=block, ids=request.values.get('ids'),
                                   weiter=request.args.get('weiter', ''))
        art = request.form.get('art')
        von, bis = _datum(request.form.get('von')), _datum(request.form.get('bis'))
        if art not in kern.ALL_TYPES or art == kern.TYPE_WORK or von is None:
            abort(400, 'Bitte Art und Zeitraum prüfen.')
        alte_tage = [e.date for e in block]
        for e in block:
            speicher.eintrag_loeschen(bid(), e.id)
        _neu_laden()
        neue_tage = _abwesenheit_anlegen(art, von, bis or von)
        speicher.tage_neu_berechnen(bid(), alte_tage + neue_tage, _neu_laden(), werte())
        db().commit()
        return _gespeichert(f'{kern.TYPE_LABELS[art]}: {len(neue_tage)} Tage gespeichert.',
                            request.form.get('weiter') or url_for('liste'))

    # --- Kalender, Statistik, Ziel ---

    @app.get('/kalender')
    @anmeldung_noetig
    def kalender():
        m = re.fullmatch(r'(\d{4})-(\d{2})', request.args.get('monat', ''))
        jahr, monat = (int(m.group(1)), int(m.group(2))) if m and 1 <= int(m.group(2)) <= 12 \
            else (heute().year, heute().month)
        vor = dt.date(jahr, monat, 1) - dt.timedelta(days=1)
        nach = dt.date(jahr + monat // 12, monat % 12 + 1, 1)
        k = aw.kalender(alle(), speicher.bereitschaften(bid()), werte(), jahr, monat, heute())
        return render_template('kalender.html', k=k, vor=vor.strftime('%Y-%m'), nach=nach.strftime('%Y-%m'),
                               monat=f'{jahr:04d}-{monat:02d}', wochentage=aw.WOCHENTAGE,
                               tag=request.args.get('tag'), saldo=aw.saldo(alle()),
                               tag_eintraege=_tag_eintraege(request.args.get('tag')))

    def _tag_eintraege(ds):
        if not _datum(ds):
            return None
        feiertag = kern.get_holidays(int(ds[:4]), werte().get('country', 'DE'), werte().get('state')).get(ds)
        bereit = [b for b in speicher.bereitschaften(bid()) if b.date <= ds <= (b.effective_end_date or b.date)]
        # Gehört der Tag zu einer mehrtägigen Abwesenheit, steht die ganze Zeitspanne da (wie in der Liste), mit
        # Bearbeiten/Löschen für den ganzen Block (Wunsch 20.10.2026)
        eintraege = sorted([e for e in alle() if e.date == ds], key=lambda e: e.start or '')
        ids = {e.id for e in eintraege}
        bloecke = [b for b in aw.bloecke(alle(), werte()) if ids & {e.id for e in b['eintraege']}]
        bloecke.sort(key=lambda b: (b['erster'].start or '', b['erster'].date))
        return {'datum': ds, 'eintraege': eintraege, 'bloecke': bloecke,
                'soll': kern.get_target_minutes_for_date(ds, alle(), werte()), 'feiertag': feiertag,
                'bereitschaft': bereit, 'anwesenheit': speicher.anwesenheit_tag(bid(), ds)}

    @app.get('/statistik')
    @anmeldung_noetig
    def statistik():
        wahl = request.args.get('jahr') or str(heute().year)
        jahr = None if wahl == 'alle' else _ganzzahl(wahl, heute().year, 1900, 2999)
        s = aw.statistik(alle(), jahr)
        if str(heute().year) not in s['jahre']:
            s['jahre'].insert(0, str(heute().year))
        return render_template('statistik.html', s=s, jahr=jahr, wahl=wahl, monat_name=_monat_name)

    @app.route('/ziel', methods=['GET', 'POST'])
    @anmeldung_noetig
    def ziel_seite():
        w = werte()
        if request.method == 'POST':
            f = request.form
            von, bis = _datum(f.get('von')), _datum(f.get('bis'))
            if f.get('aktiv') and (von is None or bis is None or bis < von):
                flash('Bitte einen gültigen Zeitraum angeben (Ende nicht vor Beginn).', 'fehler')
                return redirect(url_for('ziel_seite'))
            w['goal_active'] = bool(f.get('aktiv'))
            w['goal_start_date'] = von.isoformat() if von else ''
            w['goal_end_date'] = bis.isoformat() if bis else ''
            if f.get('stunden_berechnen') or not f.get('stunden'):
                w['goal_hours'] = aw.ziel_stunden(alle(), w, von, bis)
            else:
                w['goal_hours'] = _ganzzahl(f.get('stunden'), 0, 0, 100000)
            speicher.einstellungen_speichern(bid(), w)
            db().commit()
            return _gespeichert('Ziel gespeichert.' if w['goal_active'] else 'Ziel ausgeschaltet.', url_for('ziel_seite'))
        h = heute()
        return render_template('ziel.html', w=w, ziel=aw.ziel(alle(), w, h),
                               von=w.get('goal_start_date') or (h + dt.timedelta(days=30)).isoformat(),
                               bis=w.get('goal_end_date') or (h + dt.timedelta(days=35)).isoformat())

    # --- Bereitschaft ---

    @app.route('/bereitschaft', methods=['GET', 'POST'])
    @anmeldung_noetig
    def bereitschaft():
        if request.method == 'POST':
            f = request.form
            von, bis = _datum(f.get('von')), _datum(f.get('bis'))
            if von is None:
                flash('Bitte ein Datum angeben.', 'fehler')
                return redirect(url_for('bereitschaft'))
            bis = bis if bis and bis > von else None
            speicher.bereitschaft_anlegen(bid(), BereitschaftEntry(
                None, von.isoformat(), _uhrzeit(f.get('start')) or '', _uhrzeit(f.get('ende')) or '',
                f.get('notiz', '').strip()[:200], bis.isoformat() if bis else ''))
            db().commit()
            return _gespeichert('Bereitschaft eingetragen.', url_for('bereitschaft'))
        return render_template('bereitschaft.html', liste=speicher.bereitschaften(bid()), heute=heute().isoformat())

    @app.post('/bereitschaft/<int:b_id>/loeschen')
    @anmeldung_noetig
    def bereitschaft_loeschen(b_id):
        speicher.bereitschaft_loeschen(bid(), b_id)
        db().commit()
        return _gespeichert('Bereitschaft gelöscht.', url_for('bereitschaft'))

    # --- Mehr, Einstellungen, Austausch ---

    @app.get('/mehr')
    @anmeldung_noetig
    def mehr():
        return render_template('mehr.html', anzahl=len(alle()), per_oidc=session.get('per_oidc'))

    # --- Anwesenheit: Anmeldezeiten des Rechners, gemeldet von der Desktop-App ---

    @app.route('/anwesenheit', methods=['GET', 'POST'])
    @anmeldung_noetig
    def anwesenheit():
        neues_token = None
        if request.method == 'POST':
            f = request.form
            if f.get('aktion') == 'neu':
                name = (f.get('name') or '').strip()[:80] or 'Desktop'
                neues_token = speicher.geraet_anlegen(bid(), name)
                db().commit()
                log.info('Gerätezugang „%s“ für Benutzer %s angelegt', name, bid())
            elif f.get('aktion') == 'entfernen':
                speicher.geraet_loeschen(bid(), _ganzzahl(f.get('id'), 0))
                db().commit()
                return _gespeichert('Gerätezugang entfernt.', url_for('anwesenheit'))
        tage = speicher.anwesenheit(bid())
        monate = sorted({t['date'][:7] for t in tage}, reverse=True)
        monat = request.args.get('monat') or 'alle'
        if monat != 'alle' and not re.fullmatch(r'\d{4}-\d{2}', monat):
            monat = 'alle'
        for t in tage:
            t['dauer'] = aw.anwesend(t['start'], t['end'])
        return render_template('anwesenheit.html', tage=[t for t in tage if monat == 'alle' or t['date'].startswith(monat)],
                               monate=monate, monat=monat, geraete=speicher.geraete(bid()), neues_token=neues_token,
                               adresse=request.host_url.rstrip('/'))

    @app.get('/api/geraet/pruefen')
    @geraet_noetig
    def geraet_pruefen():
        """„Verbindung testen“ in der Desktop-App."""
        db().commit()
        return jsonify(ok=True, benutzer=g.geraet['benutzer'], geraet=g.geraet['name'], version=VERSION)

    @app.post('/api/geraet/anwesenheit')
    @geraet_noetig
    def geraet_anwesenheit():
        """Die Desktop-App meldet {"tage": [{"date": "2026-10-13", "login": "07:12", "logout": "16:03"}, …]}."""
        daten = request.get_json(silent=True)
        tage = daten.get('tage') if isinstance(daten, dict) else None
        if not isinstance(tage, list) or len(tage) > 400:
            return jsonify(fehler='Erwartet {"tage": [...]} mit höchstens 400 Tagen.'), 400
        gemeldet = 0
        for t in tage:
            tag = austausch.anwesenheit_pruefen(t.get('date'), t.get('login'), t.get('logout')) \
                if isinstance(t, dict) else None
            if tag:
                speicher.anwesenheit_melden(g.geraet['benutzer_id'], *tag)
                gemeldet += 1
        db().commit()
        return jsonify(ok=True, tage=gemeldet)

    # --- Abgleich der Einträge mit der Desktop-App (je Tag; Ablauf in abgleich.py der Desktop-App) ---------

    @app.get('/api/geraet/tage')
    @geraet_noetig
    def geraet_tage():
        """Fingerabdruck und Änderungszeit je Tag: {"tage": {"2026-10-13": {"hash": "…", "geaendert": "…"}}}."""
        stand = speicher.tage_stand(g.geraet['benutzer_id'])
        db().commit()
        return jsonify(tage=stand)

    @app.post('/api/geraet/tage/holen')
    @geraet_noetig
    def geraet_tage_holen():
        """{"daten": ["2026-10-13", …]} -> {"tage": {datum: {"inhalt", "hash", "geaendert"}}}."""
        daten = (request.get_json(silent=True) or {}).get('daten')
        if not isinstance(daten, list) or len(daten) > ABGLEICH_MAX_TAGE \
                or not all(isinstance(d, str) and kern.parse_date(d) for d in daten):
            return jsonify(fehler=f'Erwartet {{"daten": [...]}} mit höchstens {ABGLEICH_MAX_TAGE} Tagen.'), 400
        tage = speicher.tage_inhalt(g.geraet['benutzer_id'], daten)
        db().commit()
        return jsonify(tage=tage)

    @app.post('/api/geraet/tage/schreiben')
    @geraet_noetig
    def geraet_tage_schreiben():
        """{"tage": {datum: {"inhalt", "geaendert", "erwartet"}}}: ersetzt jeden Tag, dessen Server-Stand noch
        `erwartet` ist (sonst hat sich hier inzwischen etwas geändert -> abgelehnt, nächster Abgleich klärt es)."""
        tage = (request.get_json(silent=True) or {}).get('tage')
        if not isinstance(tage, dict) or len(tage) > ABGLEICH_MAX_TAGE:
            return jsonify(fehler=f'Erwartet {{"tage": {{...}}}} mit höchstens {ABGLEICH_MAX_TAGE} Tagen.'), 400
        bid_ = g.geraet['benutzer_id']
        stand = speicher.tage_stand(bid_)
        geschrieben, abgelehnt = {}, {}
        for datum, tag in tage.items():
            if kern.parse_date(datum) is None or not isinstance(tag, dict):
                abgelehnt[datum] = 'ungültig'
                continue
            if stand.get(datum, {}).get('hash', '') != tag.get('erwartet', ''):
                abgelehnt[datum] = 'geändert'
                continue
            try:
                inhalt = kern.tag_inhalt_pruefen(tag.get('inhalt'))
            except ValueError as e:
                abgelehnt[datum] = f'ungültig: {e}'
                continue
            geaendert = tag.get('geaendert')
            if not (isinstance(geaendert, str) and ZEITSTEMPEL.fullmatch(geaendert)):
                geaendert = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            speicher.tag_ersetzen(bid_, datum, inhalt, geaendert)
            geschrieben[datum] = kern.tag_hash(inhalt)
        db().commit()
        if abgelehnt:
            log.info('Abgleich %s: %d Tage abgelehnt (%s)', g.geraet['name'], len(abgelehnt),
                     ', '.join(f'{d}: {g_}' for d, g_ in sorted(abgelehnt.items())[:5]))
        return jsonify(geschrieben=geschrieben, abgelehnt=abgelehnt)

    @app.route('/einstellungen', methods=['GET', 'POST'])
    @anmeldung_noetig
    def einstellungen():
        w = werte()
        if request.method == 'POST':
            f = request.form
            roh = {
                'default_start': _uhrzeit(f.get('default_start')), 'auto_break': bool(f.get('auto_break')),
                'max_work_hours': f.get('max_work_hours'),
                'country': f.get('country'), 'state': f.get('state') or None, 'theme': f.get('theme'),
                'use_login_time': bool(f.get('use_login_time')),
                'weekday_targets': [(_uhrzeit(f.get(f'soll_{i}')) or '') if f.get(f'tag_{i}') else ''
                                    for i in range(7)],
                'special_days': [{'day': _ganzzahl(t, 0), 'month': _ganzzahl(m, 0), 'target': _uhrzeit(z) or ''}
                                 for t, m, z in zip(f.getlist('sd_tag'), f.getlist('sd_monat'), f.getlist('sd_soll'))
                                 if t.strip()],
                'break_rules': [{'after': kern.hhmm_to_minutes(_uhrzeit(n) or '00:00'), 'break': _ganzzahl(p, 0)}
                                for n, p in zip(f.getlist('br_nach'), f.getlist('br_pause')) if n.strip() and p.strip()],
            }
            roh['workdays'] = [i for i in range(7) if roh['weekday_targets'][i]]
            # Regelarbeitszeit = das häufigste Tagessoll (die Desktop-App zeigt sie als Vorgabe)
            sollwerte = [t for t in roh['weekday_targets'] if t]
            if sollwerte:
                roh['target_work_time'] = max(set(sollwerte), key=sollwerte.count)
            regeln = [k for k in speicher.STANDARD if k != 'use_login_time']   # nur Rechenregeln lösen Neuberechnung aus
            vorher = json.dumps({k: w.get(k) for k in regeln}, sort_keys=True)
            w.update(austausch.pruefen(roh))
            speicher.einstellungen_speichern(bid(), w)
            if json.dumps({k: w.get(k) for k in regeln}, sort_keys=True) != vorher:
                speicher.alles_neu_berechnen(bid())
            db().commit()
            return _gespeichert('Einstellungen gespeichert, alle Tage neu berechnet.', url_for('einstellungen'))
        import laender
        return render_template('einstellungen.html', w=w, laender=laender.laender(),
                               regionen=laender.regionen(w.get('country', 'DE')), wochentage=aw.WOCHENTAGE_LANG)

    @app.get('/api/regionen/<land>')
    @anmeldung_noetig
    def api_regionen(land):
        import laender
        return jsonify(laender.regionen(land.upper()[:2]))

    @app.route('/austausch', methods=['GET', 'POST'])
    @anmeldung_noetig
    def austausch_seite():
        if request.method == 'GET':
            return render_template('austausch.html', anzahl=len(alle()),
                                   bereitschaften=len(speicher.bereitschaften(bid())))
        db_datei, json_datei = request.files.get('datenbank'), request.files.get('einstellungen')
        hat_db = db_datei is not None and db_datei.filename
        hat_json = json_datei is not None and json_datei.filename
        if not hat_db and not hat_json:
            flash('Bitte mindestens eine Datei auswählen.', 'fehler')
            return redirect(url_for('austausch_seite'))
        if hat_db and alle() and not request.form.get('ersetzen'):
            flash('Hier sind schon Einträge vorhanden. Zum Ersetzen bitte das Häkchen setzen.', 'fehler')
            return redirect(url_for('austausch_seite'))
        try:
            neue_werte = austausch.desktop_einstellungen_lesen(json_datei.read(), speicher.UEBERNEHMEN) \
                if hat_json else None
            daten = austausch.desktop_db_lesen(db_datei.read()) if hat_db else None
        except austausch.AustauschFehler as e:
            flash(str(e), 'fehler')
            return redirect(url_for('austausch_seite'))
        teile = []
        if neue_werte is not None:
            w = werte()
            w.update(neue_werte)
            speicher.einstellungen_speichern(bid(), w)
            teile.append('Einstellungen übernommen')
        if daten is not None:
            eintraege, bereitschaften, anwesenheit = daten
            for tag in anwesenheit:   # zusammenführen statt ersetzen: der Server bekommt sie auch direkt gemeldet
                speicher.anwesenheit_melden(bid(), *tag)
            db().execute('DELETE FROM entries WHERE benutzer_id = ?', (bid(),))
            db().execute('DELETE FROM bereitschaft_entries WHERE benutzer_id = ?', (bid(),))
            for e in eintraege:
                speicher.eintrag_anlegen(bid(), e)
            for b in bereitschaften:
                speicher.bereitschaft_anlegen(bid(), b)
            teile.append(f'{len(eintraege)} Einträge, {len(bereitschaften)} Bereitschaften und '
                         f'{len(anwesenheit)} Tage Anwesenheit eingelesen')
        if neue_werte is not None and daten is None:
            speicher.alles_neu_berechnen(bid())
            teile.append('alle Tage neu berechnet')
        db().commit()
        log.info('Austausch für Benutzer %s: %s', bid(), '; '.join(teile))
        return _gespeichert('; '.join(teile) + '.', url_for('austausch_seite'))

    @app.get('/export/datenbank')
    @anmeldung_noetig
    def export_db():
        inhalt = austausch.desktop_db_schreiben(alle(), speicher.bereitschaften(bid()), speicher.anwesenheit(bid()))
        return Response(inhalt, mimetype='application/vnd.sqlite3', headers={
            'Content-Disposition': f'attachment; filename="ueberstunden_daten-{heute().isoformat()}.db"',
            'Cache-Control': 'no-store'})

    @app.get('/export/csv')
    @anmeldung_noetig
    def export_csv():
        monat = request.args.get('monat', 'alle')
        auswahl = [e for e in alle() if monat == 'alle' or e.date.startswith(monat)]
        name = 'alle' if monat == 'alle' else re.sub(r'[^0-9-]', '', monat)
        return Response(austausch.csv_schreiben(auswahl), mimetype='text/csv; charset=utf-8', headers={
            'Content-Disposition': f'attachment; filename="ueberstunden_{name}.csv"', 'Cache-Control': 'no-store'})

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def fehlerseite(e):
        return render_template('fehler.html', fehler=e), e.code


def _monat_name(monat):
    if not monat or monat == 'alle':
        return 'Alle Monate'
    return f'{aw.MONATE[int(monat[5:7]) - 1]} {monat[:4]}'


def abmelden_befehl(name):
    """python app.py abmelden <name>: alle Sitzungen einer Person beenden."""
    app = erstelle_app()
    with app.app_context():
        zeile = db().execute('SELECT id FROM benutzer WHERE name = ?', (name,)).fetchone()
        if zeile is None:
            sys.exit(f'Kein Benutzer "{name}"')
        db().execute('UPDATE benutzer SET sitzung = sitzung + 1 WHERE id = ?', (zeile['id'],))
        db().commit()
        print(f'{name}: auf allen Geräten abgemeldet')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) == 3 and sys.argv[1] == 'abmelden':
        abmelden_befehl(sys.argv[2])
    else:
        erstelle_app().run(host='127.0.0.1', port=5026, debug=True)
