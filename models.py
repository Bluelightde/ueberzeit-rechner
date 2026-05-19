
"""
Datenklassen-Modelle für die Anwendung.
"""
from dataclasses import dataclass

# pylint: disable=too-many-instance-attributes
@dataclass
class WorkEntry:
    """
    Repräsentiert einen einzelnen Arbeitseintrag.
    """
    id: int
    date: str
    start: str
    end: str
    pause: int
    minutes: int
    reason: str
    target_minutes: int = -1 # -1 means use default/settings


@dataclass
class BereitschaftEntry:
    """
    Repräsentiert einen Bereitschafts-Eintrag (On-Call).

    Ein Eintrag deckt einen zusammenhängenden Zeitraum von ``date`` bis
    ``end_date`` ab (beide Tage inklusive). Ist ``end_date`` leer oder gleich
    ``date``, handelt es sich um einen Einzeltag.

    ``start``/``end`` sind optionale Uhrzeiten. Bereitschaft beeinflusst weder
    die Pausen- noch die Überstunden-Berechnung und wird im Kalender lediglich
    als Markierung dargestellt.
    """
    id: int
    date: str
    start: str = ""
    end: str = ""
    note: str = ""
    end_date: str = ""

    @property
    def effective_end_date(self) -> str:
        """Gibt das tatsächliche End-Datum zurück (``date``, falls leer)."""
        return self.end_date or self.date
