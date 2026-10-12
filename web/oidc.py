"""Anmeldung über Authentik (OpenID Connect, Authorization Code Flow mit PKCE).

Nur Standardbibliothek. Ablauf:
  1. /anmelden/authentik leitet zu Authentik weiter (state, nonce, PKCE).
  2. Authentik leitet mit ?code=... auf /anmelden/authentik/zurueck zurück.
  3. Die App tauscht den Code serverseitig gegen ein Access-Token (mit
     Client-Secret und PKCE-Verifier) und fragt damit den Userinfo-Endpunkt.

🔑 Die Identität kommt aus dem USERINFO-Endpunkt, nicht aus dem ID-Token.
   Beide Anfragen gehen direkt von der App zu Authentik über TLS, mit dem
   Client-Secret -- ein untergeschobenes Token ist so nicht möglich, und die
   App braucht keine JWT-Bibliothek zum Prüfen von Signaturen.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

ZEITLIMIT = 10
_discovery_cache = {}  # issuer -> (zeitpunkt, daten)


class OidcFehler(Exception):
    pass


def _json_holen(url, daten=None, kopf=None):
    req = urllib.request.Request(url, data=daten, headers=dict(kopf or {}, Accept='application/json'))
    try:
        with urllib.request.urlopen(req, timeout=ZEITLIMIT) as antwort:
            return json.loads(antwort.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'replace')[:200]
        raise OidcFehler(f'Authentik antwortet mit {e.code}: {text}') from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise OidcFehler(f'Authentik nicht erreichbar: {getattr(e, "reason", e)}') from e
    except ValueError as e:
        raise OidcFehler('Antwort von Authentik ist kein JSON -- stimmt OIDC_ISSUER?') from e


def discovery(issuer):
    """Liest /.well-known/openid-configuration (eine Stunde zwischengespeichert)."""
    issuer = issuer.rstrip('/') + '/'
    treffer = _discovery_cache.get(issuer)
    if treffer and time.time() - treffer[0] < 3600:
        return treffer[1]
    daten = _json_holen(issuer + '.well-known/openid-configuration')
    for feld in ('authorization_endpoint', 'token_endpoint', 'userinfo_endpoint'):
        if feld not in daten:
            raise OidcFehler(f'Discovery-Dokument ohne {feld}.')
    _discovery_cache[issuer] = (time.time(), daten)
    return daten


def _pkce_paar():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=')
    return verifier, challenge.decode('ascii')


def anmelde_url(issuer, client_id, redirect_uri, sitzung):
    """Baut die Weiterleitung zu Authentik und merkt sich state/nonce/verifier in der Sitzung."""
    konf = discovery(issuer)
    verifier, challenge = _pkce_paar()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    sitzung['oidc'] = {'state': state, 'nonce': nonce, 'verifier': verifier, 'zeit': int(time.time())}
    parameter = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email',
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    return konf['authorization_endpoint'] + '?' + urllib.parse.urlencode(parameter)


def rueckkehr(issuer, client_id, client_secret, redirect_uri, sitzung, argumente):
    """Wertet die Rückkehr von Authentik aus. Gibt die Userinfo (dict) zurück."""
    gemerkt = sitzung.pop('oidc', None)
    if argumente.get('error'):
        raise OidcFehler(f'Authentik hat die Anmeldung abgelehnt: {argumente.get("error_description") or argumente["error"]}')
    if not gemerkt or not secrets.compare_digest(gemerkt['state'], argumente.get('state', '')):
        raise OidcFehler('Anmeldung abgelaufen oder aus einem anderen Fenster. Bitte noch einmal versuchen.')
    if time.time() - gemerkt['zeit'] > 600:
        raise OidcFehler('Anmeldung hat zu lange gedauert. Bitte noch einmal versuchen.')
    code = argumente.get('code')
    if not code:
        raise OidcFehler('Authentik hat keinen Code zurückgegeben.')

    konf = discovery(issuer)
    token = _json_holen(konf['token_endpoint'], urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
        'code_verifier': gemerkt['verifier'],
    }).encode('ascii'), {'Content-Type': 'application/x-www-form-urlencoded'})
    if 'access_token' not in token:
        raise OidcFehler('Authentik hat kein Access-Token ausgegeben.')

    info = _json_holen(konf['userinfo_endpoint'], kopf={'Authorization': f'Bearer {token["access_token"]}'})
    if not info.get('sub'):
        raise OidcFehler('Userinfo ohne "sub" -- Scope "openid" fehlt im Provider?')
    return info


def abmelde_url(issuer):
    """End-Session-Endpunkt von Authentik, falls vorhanden (sonst None)."""
    try:
        return discovery(issuer).get('end_session_endpoint')
    except OidcFehler:
        return None
