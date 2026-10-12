"""Länder und Regionen für die Feiertage -- dieselbe Auswahl wie die Desktop-App (config.py), Namen auf Deutsch."""

import functools
import gettext

import holidays as holidays_lib
import pycountry

try:
    _LAND = gettext.translation('iso3166-1', pycountry.LOCALES_DIR, languages=['de']).gettext
    _REGION = gettext.translation('iso3166-2', pycountry.LOCALES_DIR, languages=['de']).gettext
except OSError:      # ohne Übersetzungen: englische Namen
    _LAND = _REGION = str


@functools.lru_cache(maxsize=1)
def laender():
    """[(code, name)] nach Name sortiert, nur zweistellige Codes (wie config.get_country_list)."""
    aus = []
    for code in holidays_lib.list_supported_countries():
        if len(code) != 2:
            continue
        land = pycountry.countries.get(alpha_2=code)
        aus.append((code, _LAND(land.name) if land else code))
    return sorted(aus, key=lambda x: x[1])


@functools.lru_cache(maxsize=64)
def regionen(land):
    """[(code, name)] der Regionen eines Landes, ohne Städte (wie config.get_subdivisions)."""
    codes = holidays_lib.list_supported_countries().get(land, [])
    aus = []
    for code in codes:
        if len(code) <= 3 and code.upper() == code:
            region = pycountry.subdivisions.get(code=f'{land}-{code}')
            aus.append((code, _REGION(region.name) if region else code))
    return sorted(aus, key=lambda x: x[1])
