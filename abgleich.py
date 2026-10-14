"""
Einträge zwischen Desktop-App und Server-Version abgleichen -- in beide Richtungen, je Tag.

Ein Tag sind alle Einträge und Bereitschaften eines Datums (kern.tag_inhalt); beide Seiten bilden
daraus denselben Fingerabdruck (kern.tag_hash, leerer Tag = ""). Die Desktop-App merkt sich den
Fingerabdruck jedes Tages beim letzten Abgleich (Tabelle abgleich_stand) und erkennt daran, wer
etwas geändert hat:

    hier == Server                    -> gleich
    hier == letzter Stand             -> nur der Server hat geändert  -> holen
    Server == letzter Stand           -> nur hier geändert            -> senden (auch Löschen)
    beide geändert                    -> Konflikt: die neuere Änderung gewinnt (Zeit je Tag, UTC)
    kein letzter Stand (erstes Mal)   -> eine Seite leer: die andere gewinnt, sonst die neuere

Ablauf: Die Oberfläche liest den hiesigen Stand (SQLite nur im GUI-Thread), ausfuehren() spricht im
Hintergrund mit dem Server und gibt zurück, was übernommen werden soll; die Oberfläche schreibt es
dann selbst (DBManager.tag_ersetzen) und merkt sich den neuen gemeinsamen Stand.

Der Server ersetzt einen Tag nur, wenn er dort noch so aussieht wie beim Planen; sonst lehnt er ab
und der nächste Abgleich klärt es. Nur Standardbibliothek, ohne Qt.
"""
import logging

import kern
from server_sync import ServerFehler, anfrage

logger = logging.getLogger(__name__)

PAKET = 200         # Tage je Anfrage (der Server nimmt bis zu 1000)


def planen(lokal, stand, server):
    """lokal/server: {datum: {"hash", "geaendert"}}, stand: {datum: hash} beim letzten Abgleich.

    -> {"senden": [...], "holen": [...], "gleich": [...], "konflikte": [...]} (Konflikte stehen
    zusätzlich unter senden oder holen, je nachdem, welche Seite gewinnt)."""
    plan = {"senden": [], "holen": [], "gleich": [], "konflikte": []}
    for datum in sorted(set(lokal) | set(server) | set(stand)):
        hier, dort = lokal.get(datum, {}), server.get(datum, {})
        h_hier, h_dort, h_vorher = hier.get("hash", ""), dort.get("hash", ""), stand.get(datum)
        if h_hier == h_dort:
            plan["gleich"].append(datum)
        elif h_vorher is not None and h_hier == h_vorher:
            plan["holen"].append(datum)
        elif h_vorher is not None and h_dort == h_vorher:
            plan["senden"].append(datum)
        elif h_vorher is None and not h_hier:
            plan["holen"].append(datum)
        elif h_vorher is None and not h_dort:
            plan["senden"].append(datum)
        else:
            plan["konflikte"].append(datum)
            hier_neuer = hier.get("geaendert", "") >= dort.get("geaendert", "")
            plan["senden" if hier_neuer else "holen"].append(datum)
    return plan


def _pakete(liste):
    for i in range(0, len(liste), PAKET):
        yield liste[i:i + PAKET]


def ausfuehren(adresse, token, lokal, stand):
    """Ein Abgleich. lokal: DBManager.tage_lokal(), stand: DBManager.abgleich_stand().

    -> {"holen": {datum: {"inhalt", "hash", "geaendert", "vorher"}},  # vorher = Hash hier
        "stand": {datum: hash},                                       # neuer gemeinsamer Stand
        "gesendet": n, "abgelehnt": n, "konflikte": [datum, ...]}
    Wirft ServerFehler (Netz, Zugang, falsche Adresse)."""
    server = anfrage(adresse, token, "/api/geraet/tage").get("tage")
    if not isinstance(server, dict):
        raise ServerFehler("Der Server kennt den Abgleich der Einträge noch nicht "
                           "(Version zu alt?).")
    plan = planen(lokal, stand, server)
    leer = kern.tag_inhalt()
    ergebnis = {"holen": {}, "stand": {}, "gesendet": 0, "abgelehnt": 0,
                "konflikte": plan["konflikte"]}
    for datum in plan["gleich"]:
        ergebnis["stand"][datum] = lokal.get(datum, {}).get("hash", "")

    for paket in _pakete(plan["senden"]):
        tage = {d: {"inhalt": lokal.get(d, {}).get("inhalt", leer),
                    "geaendert": lokal.get(d, {}).get("geaendert", ""),
                    "erwartet": server.get(d, {}).get("hash", "")} for d in paket}
        antwort = anfrage(adresse, token, "/api/geraet/tage/schreiben", {"tage": tage})
        for datum, h in (antwort.get("geschrieben") or {}).items():
            if datum in tage:
                ergebnis["stand"][datum] = h
                ergebnis["gesendet"] += 1
        abgelehnt = antwort.get("abgelehnt") or {}
        ergebnis["abgelehnt"] += len(abgelehnt)
        for datum, grund in abgelehnt.items():
            logger.info("Abgleich: Server lehnt %s ab (%s)", datum, grund)

    for paket in _pakete(plan["holen"]):
        antwort = anfrage(adresse, token, "/api/geraet/tage/holen",
                          {"daten": paket}).get("tage") or {}
        for datum in paket:
            tag = antwort.get(datum)
            try:
                inhalt = kern.tag_inhalt_pruefen(
                    tag.get("inhalt") if isinstance(tag, dict) else None)
            except ValueError as e:
                logger.warning("Abgleich: Tag %s vom Server unbrauchbar: %s", datum, e)
                continue
            ergebnis["holen"][datum] = {"inhalt": inhalt, "hash": kern.tag_hash(inhalt),
                                        "geaendert": tag.get("geaendert") or "",
                                        "vorher": lokal.get(datum, {}).get("hash", "")}
    return ergebnis


def uebernehmen(db, ergebnis):
    """Im GUI-Thread: geholte Tage schreiben und den gemeinsamen Stand merken -> Zahl der Tage.

    Ein Tag, der hier seit dem Planen geändert wurde, wird übersprungen (der nächste Abgleich
    sendet ihn)."""
    stand = dict(ergebnis["stand"])
    geholt = 0
    for datum, tag in ergebnis["holen"].items():
        if db.tag_hash(datum) != tag["vorher"]:
            continue
        db.tag_ersetzen(datum, tag["inhalt"], tag["geaendert"])
        stand[datum] = tag["hash"]
        geholt += 1
    db.abgleich_stand_setzen(stand)
    return geholt
