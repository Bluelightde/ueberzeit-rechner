"""
Anwesenheit an die Server-Version (web/) melden.

Die Server-Version kann die Anmeldezeiten dieses Rechners nicht selbst lesen. Die Desktop-App liest sie
(logic.get_system_sessions → Tabelle device_login) und schickt sie mit einem Gerätezugang an den Server:

    POST <adresse>/api/geraet/anwesenheit   Authorization: Bearer uz_…
    {"tage": [{"date": "2026-10-13", "login": "07:12", "logout": "16:03"}, …]}

Der Server führt zusammen wie die Desktop-App (frühester Login, spätester Logout je Tag). Der Gerätezugang
darf nur melden, nichts lesen. Nur Standardbibliothek, ohne Qt -- läuft im Hintergrund-Thread.
"""
import json
import logging
import urllib.error
import urllib.request

from netz import ssl_kontext

logger = logging.getLogger(__name__)

TAGE = 62           # so viele zurückliegende Tage werden jedes Mal mitgeschickt (verpasste Meldungen holen sich nach)
WARTEZEIT = 10      # Sekunden


class ServerFehler(Exception):
    """Verständliche Fehlermeldung für Protokoll und Einstellungsdialog."""


def _anfrage(adresse, token, pfad, daten=None, wartezeit=WARTEZEIT):
    adresse = (adresse or "").strip().rstrip("/")
    if not adresse.startswith(("http://", "https://")):
        raise ServerFehler("Die Adresse muss mit http:// oder https:// beginnen.")
    if not (token or "").strip():
        raise ServerFehler("Kein Gerätezugang eingetragen.")
    kopf = {"Authorization": f"Bearer {token.strip()}", "Accept": "application/json",
            "User-Agent": "Ueberzeit-Desktop"}
    rumpf = None
    if daten is not None:
        rumpf = json.dumps(daten).encode("utf-8")
        kopf["Content-Type"] = "application/json"
    anfrage = urllib.request.Request(adresse + pfad, data=rumpf, headers=kopf,
                                     method="POST" if rumpf is not None else "GET")
    try:
        with urllib.request.urlopen(anfrage, timeout=wartezeit, context=ssl_kontext()) as antwort:   # nosec: Adresse stellt die Person ein
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ServerFehler("Gerätezugang unbekannt oder entfernt – in der Server-Version unter "
                               "„Anwesenheit“ einen neuen anlegen.") from e
        if e.code == 404:
            raise ServerFehler("Unter dieser Adresse läuft keine passende Überzeit-Server-Version.") from e
        if e.code == 405:   # http:// auf https:// umgeleitet, dabei wurde aus POST ein GET
            raise ServerFehler("Der Server leitet um – bitte die Adresse mit https:// eintragen.") from e
        if e.code == 429:
            raise ServerFehler("Zu viele Fehlversuche – der Server wartet 15 Minuten.") from e
        raise ServerFehler(f"Der Server antwortet mit Fehler {e.code}.") from e
    except urllib.error.URLError as e:
        raise ServerFehler(f"Server nicht erreichbar: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise ServerFehler(f"Server nicht erreichbar: {e}") from e
    except ValueError as e:
        raise ServerFehler("Unter dieser Adresse läuft keine passende Überzeit-Server-Version.") from e


def verbindung_testen(adresse, token):
    """Für den Knopf „Verbindung testen“: Text bei Erfolg, sonst ServerFehler."""
    antwort = _anfrage(adresse, token, "/api/geraet/pruefen", wartezeit=5)
    return f"Verbunden als „{antwort.get('benutzer', '?')}“ (Gerät „{antwort.get('geraet', '?')}“)."


def tage_auswaehlen(device_logins, heute, heute_login=None, tage=TAGE):
    """device_login-Zeilen ({'date', 'start', 'end'}, neueste zuerst) -> Meldung für den Server.

    heute_login: Anmeldezeit von heute (logic.get_login_time), falls device_login sie noch nicht hat."""
    liste = [{"date": d["date"], "login": d.get("start") or "", "logout": d.get("end") or ""}
             for d in device_logins if d.get("date") and (d.get("start") or d.get("end"))]
    liste.sort(key=lambda d: d["date"], reverse=True)
    liste = liste[:tage]
    if heute_login:
        eintrag = next((d for d in liste if d["date"] == heute), None)
        if eintrag is None:
            liste.insert(0, {"date": heute, "login": heute_login, "logout": ""})
        elif not eintrag["login"]:
            eintrag["login"] = heute_login
    return liste


def anwesenheit_senden(adresse, token, tage):
    """Schickt die Tage; gibt die Zahl der angenommenen Tage zurück oder wirft ServerFehler."""
    if not tage:
        return 0
    antwort = _anfrage(adresse, token, "/api/geraet/anwesenheit", {"tage": tage})
    return int(antwort.get("tage", 0))
