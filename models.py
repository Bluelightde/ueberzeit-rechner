
"""
Datenklassen-Modelle für die Anwendung.
"""
from dataclasses import dataclass

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
