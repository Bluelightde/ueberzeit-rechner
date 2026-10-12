"""gunicorn-Einstellungen von Überzeit."""
import os

bind = f'0.0.0.0:{os.environ.get("PORT", "5026")}'
workers = int(os.environ.get('WORKERS', '2'))
threads = 2
timeout = 60   # Einlesen einer großen Desktop-Datenbank samt Neuberechnung darf etwas dauern

# 🔑 preload_app: erstelle_app() läuft EINMAL im Hauptprozess -- sonst legten beim allerersten Start zwei Worker
#    gleichzeitig den Notzugang an (UNIQUE(name)), und im Protokoll stünden zwei Startpasswörter.
preload_app = True

accesslog = '-'
errorlog = '-'
# Keine Abfrageparameter ins Zugriffsprotokoll (?code= von Authentik)
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
