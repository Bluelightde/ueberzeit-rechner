
"""
Benutzerdefinierte UI-Komponenten, Delegaten und UI-Hilfsfunktionen.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate

from logic import COLOR_POSITIVE, COLOR_NEGATIVE


def overtime_qcolor(minutes):
    """Gibt eine halb-transparente QColor für Heatmap-Zellen zurück.

    Positive Minuten → Grün, negative → Rot.
    Die Transparenz steigt mit dem Betrag der Minuten.

    Args:
        minutes: Überstunden-Minuten (positiv oder negativ, nicht 0).

    Returns:
        QColor mit passendem Farbton und Alpha-Kanal.
    """
    alpha = min(255, 60 + abs(minutes) * 2)
    if minutes > 0:
        return QColor(16, 185, 129, alpha)   # #10b981
    return QColor(239, 68, 68, alpha)        # #ef4444


def set_overtime_color(widget, minutes):
    """Setzt die Textfarbe eines Widgets anhand des Überstunden-Vorzeichens.

    Positiv → grün, negativ → rot, null → Standard (kein Stylesheet).

    Args:
        widget:  QWidget mit setStyleSheet()-Methode (z.B. QLabel).
        minutes: Überstunden-Minuten.
    """
    if minutes > 0:
        widget.setStyleSheet(f"color: {COLOR_POSITIVE};")
    elif minutes < 0:
        widget.setStyleSheet(f"color: {COLOR_NEGATIVE};")
    else:
        widget.setStyleSheet("")

# pylint: disable=too-few-public-methods
class HeatmapDelegate(QStyledItemDelegate):
    """
    Delegate zum Zeichnen eines blauen Rahmens um den heutigen Tag in der Heatmap.
    """
    def paint(self, painter: QPainter, option, index):
        """
        Zeichnet die Zelle und fügt einen Rahmen hinzu, wenn es der heutige Tag ist.
        """
        super().paint(painter, option, index)

        is_today = index.data(Qt.ItemDataRole.UserRole + 1)

        if is_today:
            pen = QPen(QColor("#60a5fa"), 2)  # Blauer Rahmen für den heutigen Tag
            painter.setPen(pen)
            r = option.rect
            painter.drawRect(r.x() + 1, r.y() + 1, r.width() - 2, r.height() - 2)
