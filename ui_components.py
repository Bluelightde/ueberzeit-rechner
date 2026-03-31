
"""
Benutzerdefinierte UI-Komponenten und Delegaten.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate

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
