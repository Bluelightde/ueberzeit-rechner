
"""
Konfigurations- und Pfadeinstellungen für die Anwendung.
"""
import os
import sys
import holidays as holidays_lib
import pycountry

# Anwendungsversion (zentrale Quelle für das "Über"-Fenster, Builds usw.)
APP_VERSION = "1.5.0"

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
LOG_FILE = os.path.join(BASE_DIR, "ueberstunden.log")
ICON_PATH = os.path.join(BUNDLE_DIR, "icon.png")

BUNDESLAENDER = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg",
    "HB": "Bremen", "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz",
    "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein", "TH": "Thüringen"
}


def get_country_list():
    """Gibt sortierte Liste der von der holidays-Bibliothek unterstützten Länder zurück.

    Nur ISO 3166-1 Alpha-2 Codes (2 Buchstaben) werden berücksichtigt.
    Rückgabe: Liste von (code, anzeigename) Tupeln, sortiert nach Name.
    """
    alpha2_codes = (c for c in holidays_lib.list_supported_countries().keys() if len(c) == 2)
    result = []
    for code in alpha2_codes:
        country = pycountry.countries.get(alpha_2=code)
        name = country.name if country else code
        result.append((code, name))
    return sorted(result, key=lambda x: x[1])


def get_subdivisions(country_code):
    """Gibt sortierte Liste der Regionen/Bundesländer für ein Land zurück.

    Filtert nicht-standard Einträge heraus (z.B. 'Augsburg' in DE).
    Rückgabe: Liste von (code, anzeigename) Tupeln, oder leere Liste falls keine Regionen.
    """
    all_subdivs = holidays_lib.list_supported_countries().get(country_code, [])
    # Nur standard Codes behalten (max. 3 Großbuchstaben/Ziffern, keine Städtenamen)
    subdiv_codes = (c for c in all_subdivs if len(c) <= 3 and c.upper() == c)
    result = []
    for code in subdiv_codes:
        subdiv = pycountry.subdivisions.get(code=f"{country_code}-{code}")
        name = subdiv.name if subdiv else code
        result.append((code, name))
    return sorted(result, key=lambda x: x[1])
