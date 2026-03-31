
"""
Konfigurations- und Pfadeinstellungen für die Anwendung.
"""
import os
import sys

# --- KONFIGURATION & PFADE (PyInstaller-kompatibel) ---
if getattr(sys, 'frozen', False):
    if sys.platform == 'darwin':
        BASE_DIR = os.path.abspath(os.path.join(sys.executable, '..', '..', '..', '..'))
    else:
        BASE_DIR = os.path.dirname(sys.executable)
    # pylint: disable=protected-access
    BUNDLE_DIR = sys._MEIPASS if hasattr(sys, '_MEIPASS') else BASE_DIR
    # Matplotlib Font-Cache in einen persistenten Ordner leiten,
    # sonst wird er bei jedem Start neu gebaut → starke Verzögerung.
    os.environ.setdefault('MPLCONFIGDIR', os.path.join(BASE_DIR, '.mplconfig'))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

DB_FILE = os.path.join(BASE_DIR, "ueberstunden_daten.db")
SETTINGS_FILE = os.path.join(BASE_DIR, "ueberstunden_settings.json")
ICON_PATH = os.path.join(BUNDLE_DIR, "icon.png")

BUNDESLAENDER = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg",
    "HB": "Bremen", "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz",
    "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein", "TH": "Thüringen"
}
