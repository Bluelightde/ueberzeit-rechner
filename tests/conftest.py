"""
Pytest-Konfiguration: Fügt das Projektverzeichnis zum sys.path hinzu,
damit die Module ohne Installation importiert werden können.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
