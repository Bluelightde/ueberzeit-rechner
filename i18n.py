"""
Internationalisierung (i18n) für den Überstunden-Rechner.

Nutzung:
    from i18n import tr
    label = QLabel(tr("Einstellungen"))

setup_i18n() muss einmalig nach QApplication-Erstellung aufgerufen werden.
"""
from __future__ import annotations

from PyQt6.QtCore import QLocale

_lang = "de"  # pylint: disable=invalid-name

# Englische Übersetzungen (Schlüssel = deutscher Originaltext)
_EN: dict[str, str] = {
    # --- Dialogs: SettingsDialog ---
    "Einstellungen": "Settings",
    "Tages-Standardwerte:": "Daily defaults:",
    "Login-Zeit als Startzeit verwenden": "Use login time as start time",
    (
        "Liest beim Programmstart die letzte Anmeldezeit des Benutzers aus.\n"
        "Die Standard-Startzeit dient als Fallback, falls die Anmeldezeit\n"
        "nicht ermittelt werden kann."
    ): (
        "Reads the last login time of the user at program start.\n"
        "The default start time is used as fallback if the login time\n"
        "cannot be determined."
    ),
    "Pausen-Regelung:": "Break rules:",
    "Automatische Pausen-Berechnung": "Automatic break calculation",
    "Darstellung:": "Appearance:",
    "Dark Mode aktivieren": "Enable dark mode",
    "Farbe der Bereitschaftslinie:": "On-call line color:",
    "Farbe wählen": "Choose color",
    "Zurücksetzen": "Reset",
    "Speichern": "Save",
    "Arbeitstage (Soll-Tage):": "Work days (target days):",
    "Fallback Startzeit:": "Fallback start time:",
    "Regelarbeitszeit (Soll):": "Target work time:",
    "Max. anrechenbare Arbeitszeit:": "Max. countable work time:",
    "Ab Arbeitszeit (h:mm)": "After work time (h:mm)",
    "Pause (min)": "Break (min)",
    "Hinzufügen": "Add",
    "Löschen": "Delete",
    "Bearbeiten": "Edit",
    "Regionales:": "Regional:",
    "Land:": "Country:",
    "Region (für Feiertage):": "Region (for holidays):",
    "Sonder-Arbeitstage (z.B. 24.12.):": "Special work days (e.g. Dec 24):",
    "Tag": "Day",
    "Monat": "Month",
    "Soll-Zeit": "Target time",
    "Speicherort der Datenbank:": "Database location:",
    "Durchsuchen…": "Browse…",

    # --- Dialogs: EditDialog ---
    "Eintrag bearbeiten": "Edit entry",
    "Start- und Endzeit verwenden": "Use start and end time",
    "Start:": "Start:",
    "Ende:": "End:",
    "Pause:": "Break:",
    "Minuten (Überstunden):": "Minutes (overtime):",
    "Anlass:": "Reason:",
    "Individuelles Tagessoll für diesen Tag": "Individual daily target for this day",
    "Datum:": "Date:",
    "SQLite Datenbank (*.db);;Alle Dateien (*)": "SQLite Database (*.db);;All Files (*)",
    "SQLite-Datenbank (*.db);;Alle Dateien (*)": "SQLite Database (*.db);;All Files (*)",
    "Datenbank speichern unter": "Save database as",

    # --- MainTab: Eingabe ---
    "Gesamt-Saldo:": "Total balance:",
    "Aktuelle Uhrzeit als Startzeit setzen": "Set current time as start time",
    "Aktuelle Uhrzeit als Endzeit setzen": "Set current time as end time",
    "z.B. Regulär": "e.g. Regular",
    "Eintragen": "Add entry",
    "Indiv. Tagessoll:": "Indiv. daily target:",
    "Berechne...": "Calculating...",
    "Filter:": "Filter:",
    "Alle": "All",
    "CSV Import": "CSV Import",
    "Export": "Export",
    "CSV  (.csv)": "CSV  (.csv)",
    "Excel (.xlsx)": "Excel (.xlsx)",
    "PDF  (.pdf)": "PDF  (.pdf)",
    "Jetzt": "Now",

    # --- MainTab: Tabelle ---
    "Datum": "Date",
    "Zeitraum": "Period",
    "Überstunden": "Overtime",
    "Anlass": "Reason",
    "Aktion": "Action",

    # --- MainTab: Live-Berechnung ---
    "Netto (Tag): {net} ➔ <b>{ot} Überstunden (Tag-Saldo)</b>": (
        "Net (day): {net} ➔ <b>{ot} overtime (day balance)</b>"
    ),
    "⚠️ Max. {h}h erreicht!": "⚠️ Max. {h}h reached!",
    "⚠️ Ruhezeit verletzt ({r}h < 11h)": "⚠️ Rest period violated ({r}h < 11h)",
    "Überschneidung mit bestehendem Eintrag:": "Overlap with existing entry:",

    # --- MainTab: Dialoge / Meldungen ---
    "Löschen bestätigen": "Confirm deletion",
    "Eintrag vom {d} wirklich löschen?": "Really delete entry from {d}?",
    "Überschneidung": "Overlap",
    (
        "Dieser Zeitraum überschneidet sich mit einem existierenden Eintrag:"
        "\n\n{overlap}\n\nBitte korrigiere die Zeiten."
    ): (
        "This period overlaps with an existing entry:"
        "\n\n{overlap}\n\nPlease correct the times."
    ),
    (
        "Die Änderungen überschneiden sich mit einem anderen Eintrag:"
        "\n\n{overlap}\n\nBitte korrigiere die Zeiten."
    ): (
        "The changes overlap with another entry:"
        "\n\n{overlap}\n\nPlease correct the times."
    ),
    "Ohne Anlass": "No reason",
    "Erfolg": "Success",
    "Fehler": "Error",

    # --- MainTab: Export ---
    "Alle Einträge": "All entries",
    "Monat {m}": "Month {m}",
    "CSV Export": "CSV Export",
    "CSV Dateien (*.csv)": "CSV Files (*.csv)",
    "Gesamt": "Total",
    "CSV erfolgreich exportiert!": "CSV exported successfully!",
    "Fehler beim CSV-Export:\n{ex}": "Error during CSV export:\n{ex}",
    "Excel Export": "Excel Export",
    "Excel Dateien (*.xlsx)": "Excel Files (*.xlsx)",
    "openpyxl ist nicht installiert.\nBitte ausführen: pip install openpyxl": (
        "openpyxl is not installed.\nPlease run: pip install openpyxl"
    ),
    "Überstunden-Nachweis – {title}": "Overtime Record – {title}",
    "Gesamtsumme:": "Total:",
    "Excel-Datei erfolgreich exportiert!": "Excel file exported successfully!",
    "Fehler beim Excel-Export:\n{ex}": "Error during Excel export:\n{ex}",
    "PDF Export": "PDF Export",
    "PDF Dateien (*.pdf)": "PDF Files (*.pdf)",
    "Überstunden-Nachweis": "Overtime Record",
    "Erstellt am {d}": "Created on {d}",
    "PDF erfolgreich exportiert!": "PDF exported successfully!",
    "Fehler beim PDF-Export:\n{ex}": "Error during PDF export:\n{ex}",
    "Dauer": "Duration",

    # --- MainTab: Import ---
    "Import": "Import",
    "Keine importierbaren Einträge gefunden.": "No importable entries found.",
    "Import bestätigen": "Confirm import",
    (
        "{n} Einträge gefunden:\n\n{preview}"
        "\n\nJetzt importieren?\n"
        "(Überstunden werden automatisch für jeden Tag berechnet/konsolidiert)"
    ): (
        "{n} entries found:\n\n{preview}"
        "\n\nImport now?\n"
        "(Overtime will be automatically calculated/consolidated for each day)"
    ),
    "… und {n} weitere": "… and {n} more",
    (
        "{n} Einträge importiert!\n"
        "Tagessalden wurden automatisch berechnet.\n"
        "Backup der Datenbank angelegt."
    ): (
        "{n} entries imported!\n"
        "Daily balances have been calculated automatically.\n"
        "Database backup created."
    ),
    "Fehler beim Import:\n{ex}": "Error during import:\n{ex}",

    # --- GoalsTab ---
    "Zeitraum und Überstunden-Ziel konfigurieren": "Configure period and overtime goal",
    "Gleitzeit-Ziel aktivieren (Urlaubs-Sparer)": "Enable flextime goal (vacation saver)",
    (
        "💡 Aktiviere das Gleitzeit-Ziel, um deinen Fortschritt beim Ansparen "
        "von Überstunden zu verfolgen – z.B. für einen Urlaub oder freien Tag."
    ): (
        "💡 Enable the flextime goal to track your progress saving up overtime "
        "— e.g. for a vacation or a day off."
    ),
    "Urlaub / Frei von:": "Vacation / Off from:",
    "bis:": "to:",
    " | Benötigte Überstunden:": " | Required overtime:",
    "Fortschritts-Dashboard": "Progress dashboard",
    "Aktueller Stand": "Current status",
    "Es fehlen noch": "Still missing",
    "Arbeitstage zum Ansparen": "Work days to save up",
    "{p}% erreicht": "{p}% reached",
    (
        "🎉 Herzlichen Glückwunsch! "
        "Du hast genug Überstunden für diesen Zeitraum angespart!"
    ): (
        "🎉 Congratulations! "
        "You have saved up enough overtime for this period!"
    ),
    "⚠️ Der gewünschte Zeitraum hat bereits begonnen oder ist heute!": (
        "⚠️ The desired period has already started or is today!"
    ),
    "Keine regulären Arbeitstage mehr zum Ansparen übrig!": (
        "No more regular work days left to save up!"
    ),
    (
        "Tipp: Wenn du ab sofort jeden Tag "
        "<b>{m} Minuten</b> länger machst, "
        "erreichst du dein Ziel punktgenau."
    ): (
        "Tip: If you work "
        "<b>{m} minutes</b> longer every day from now on, "
        "you will reach your goal exactly."
    ),

    # --- Welcome dialog ---
    "Willkommen": "Welcome",
    "Willkommen beim Überzeit Rechner": "Welcome to Überzeit Rechner",
    (
        "Bitte triff ein paar grundlegende Einstellungen, "
        "damit die App von Anfang an korrekt rechnet."
    ): (
        "Please configure a few basics so the app "
        "calculates correctly from the start."
    ),
    "Überspringen": "Skip",
    "Los geht's →": "Get Started →",
    "Einrichtungsassistenten erneut aufrufen": "Run Setup Wizard Again",

    # --- Über-Fenster ---
    "Über das Programm": "About",
    "Über Überzeit Rechner": "About Überzeit Rechner",
    "Überstunden- und Arbeitszeit-Rechner": "Overtime and working-time calculator",
    "© 2026 Micha Weiß · MIT-Lizenz": "© 2026 Micha Weiß · MIT License",
    "Schließen": "Close",

    # --- Settings section headers ---
    "Arbeitszeit && Pause": "Working time && Break",
    "Region && Feiertage": "Region && Holidays",
    "System && Design": "System && Appearance",
    "⚠️ Mitternachtsschicht: Wird als ein Eintrag dem Starttag zugerechnet.": (
        "⚠️ Midnight shift: Counted as a single entry on the start day."
    ),

    # --- Sprache ---
    "Sprache:": "Language:",
    "(Neustart erforderlich)": "(restart required)",

    # --- CalendarTab ---
    "< Vorheriger": "< Previous",
    "Nächster >": "Next >",
    "Heute": "Today",
    "Monat:": "Month:",
    "Monats-Saldo: {s}": "Monthly balance: {s}",

    # --- BereitschaftTab ---
    "Bereitschaft": "On-Call",
    "Bereitschaft bearbeiten": "Edit on-call",
    "Mit Uhrzeiten": "With times",
    "Bis:": "To:",
    "Uhrzeit": "Time",
    "Notiz:": "Note:",
    "Notiz": "Note",
    "Notiz (optional)": "Note (optional)",
    "ganztägig": "all day",
    "Bereitschaft vom {d} wirklich löschen?": "Really delete on-call from {d}?",

    # --- StatsTab ---
    "Keine Daten vorhanden": "No data available",
    "Überstunden (in Stunden)": "Overtime (in hours)",
    "Monatlicher Überstunden-Verlauf": "Monthly overtime trend",
    "Gesamt-Saldo": "Total balance",
    "⌀ pro Monat": "Avg. per month",
    "Bester Monat": "Best month",
    "Schlechtester Monat": "Worst month",
    "Längste Plus-Serie": "Longest plus streak",
    "Längste Minus-Serie": "Longest minus streak",
    "{n} Tage": "{n} days",
    "Zeitraum:": "Period:",
    "Letzte 12 Monate": "Last 12 months",
    "Aktuelles Jahr": "Current year",
    "Vorheriges Jahr": "Previous year",
    "Kumulativer Saldo (Stunden)": "Cumulative balance (hours)",
    "Saldo-Verlauf (Monats-Schlussstand) — aktuell {h:+.1f}h": (
        "Balance over time (month-end) — current {h:+.1f}h"
    ),
    "⚠ {n} Einträge ohne Datum (Summe {h:+.1f}h) nicht im Verlauf enthalten": (
        "⚠ {n} entries without date (sum {h:+.1f}h) not included in trend"
    ),
    "Stunden": "Hours",
    "Monatlicher Saldo (Stunden)": "Monthly balance (hours)",
    "⌀ Saldo je Wochentag (h)": "Avg. balance per weekday (h)",

    # --- Main window ---
    "Eingabe && Liste": "Input && List",
    "Ziele && Dashboard": "Goals && Dashboard",
    "Kalender-Heatmap": "Calendar Heatmap",
    "Diagramm && Statistik": "Chart && Statistics",

    # --- DB not found dialog ---
    "Datenbank nicht gefunden": "Database not found",
    (
        "Die Datenbankdatei wurde nicht gefunden:\n{path}\n\n"
        "Bitte wähle eine vorhandene Datenbankdatei oder einen neuen Speicherort."
    ): (
        "The database file was not found:\n{path}\n\n"
        "Please select an existing database file or a new location."
    ),
    "Datei auswählen…": "Select file…",
    "Neu erstellen": "Create new",
    "Abbrechen": "Cancel",
    "Datenbankdatei auswählen": "Select database file",
    "Neue Datenbankdatei anlegen": "Create new database file",

    # --- Move DB dialog ---
    "Datenbank verschieben?": "Move database?",
    (
        "Soll die bestehende Datenbank an den neuen Ort verschoben werden?\n"
        "(Bei 'Nein' wird am neuen Ort eine neue, leere Datenbank erstellt.)"
    ): (
        "Should the existing database be moved to the new location?\n"
        "(If 'No', a new empty database will be created at the new location.)"
    ),
    "Datenbank konnte nicht verschoben werden:\n{e}": (
        "Database could not be moved:\n{e}"
    ),
}

TRANSLATIONS: dict[str, dict[str, str]] = {"en": _EN}

# Anzeigenamen der verfügbaren Sprachen (Code → nativer Name)
LANGUAGE_NAMES: dict[str, str] = {
    "de": "Deutsch",
    "en": "English",
}


def available_languages() -> list[tuple[str, str]]:
    """Gibt eine sortierte Liste aller verfügbaren Sprachen zurück: [(code, name), ...]."""
    langs = [("de", LANGUAGE_NAMES["de"])] + [
        (code, LANGUAGE_NAMES.get(code, code))
        for code in TRANSLATIONS
        if code != "de"
    ]
    return langs


def setup_i18n(lang: str | None = None) -> None:
    """Stellt die aktive Sprache ein.

    lang:  Sprachcode ('de', 'en', …) aus den gespeicherten Einstellungen.
           None → Systemsprache erkennen, bei unbekannter Sprache 'de' als Fallback.
    Muss nach QApplication-Erstellung aufgerufen werden.
    """
    global _lang  # pylint: disable=global-statement
    if lang and lang in TRANSLATIONS:
        _lang = lang
    elif lang == "de":
        _lang = "de"
    else:
        system_lang = QLocale.system().name()[:2].lower()
        _lang = system_lang if system_lang in TRANSLATIONS else "de"


def current_language() -> str:
    """Gibt den aktiven Sprachcode zurück (z.B. 'de' oder 'en')."""
    return _lang


def get_locale() -> QLocale:
    """Gibt eine QLocale passend zur aktiven App-Sprache zurück.

    Wird für Datums-/Uhrzeitformate und Wochentagsnamen verwendet,
    damit Format und Sprache übereinstimmen.
    """
    if _lang == "de":
        return QLocale(QLocale.Language.German)
    if _lang == "en":
        return QLocale(QLocale.Language.English)
    return QLocale.system()


def tr(text: str) -> str:
    """Gibt den übersetzten Text zurück.

    Falls keine Übersetzung gefunden wird, wird der Originaltext zurückgegeben.
    """
    if _lang == "de":
        return text
    return TRANSLATIONS.get(_lang, {}).get(text, text)
