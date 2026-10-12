#!/usr/bin/env python3
"""Sichert die Datenbank der Überzeit konsistent, auch im laufenden Betrieb.

Aufruf:  python3 sicherung.py [DATENBANK] [ZIELORDNER] [ANZAHL]
Standard: daten/ueberzeit.db -> daten/sicherung/, die letzten 14 bleiben.

🔑 sqlite3.backup() statt cp: Die App schreibt im WAL-Modus. Eine einfache
   Dateikopie kann einen halben Stand erwischen (Hauptdatei ohne die
   Änderungen in ueberzeit.db-wal). Die Backup-API liest einen in sich
   stimmigen Stand, während die App weiterläuft.
"""

import datetime as dt
import os
import sqlite3
import sys

hier = os.path.dirname(os.path.abspath(__file__))
quelle = sys.argv[1] if len(sys.argv) > 1 else os.path.join(hier, 'daten', 'ueberzeit.db')
ziel_ordner = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(quelle), 'sicherung')
behalten = int(sys.argv[3]) if len(sys.argv) > 3 else 14

if not os.path.exists(quelle):
    sys.exit(f'Keine Datenbank unter {quelle}')
os.makedirs(ziel_ordner, mode=0o750, exist_ok=True)

ziel = os.path.join(ziel_ordner, f'ueberzeit-{dt.datetime.now():%Y-%m-%d_%H%M}.db')
alt = sqlite3.connect(f'file:{quelle}?mode=ro', uri=True)
neu = sqlite3.connect(ziel)
with neu:
    alt.backup(neu)
pruefung = neu.execute('PRAGMA integrity_check').fetchone()[0]
anzahl = neu.execute('SELECT COUNT(*) FROM entries').fetchone()[0]
neu.close()
alt.close()
os.chmod(ziel, 0o600)  # Arbeitszeiten
if pruefung != 'ok':
    sys.exit(f'Sicherung {ziel} ist beschädigt: {pruefung}')

# Alte Sicherungen aufräumen (nach Name sortiert = nach Datum)
vorhanden = sorted(f for f in os.listdir(ziel_ordner) if f.startswith('ueberzeit-') and f.endswith('.db'))
for datei in vorhanden[:-behalten]:
    os.remove(os.path.join(ziel_ordner, datei))

print(f'Gesichert: {ziel} ({anzahl} Einträge, integrity_check ok), {min(len(vorhanden), behalten)} Sicherungen vorhanden')
