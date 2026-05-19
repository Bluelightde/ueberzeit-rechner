
"""
Benutzerdefinierte UI-Komponenten, Delegaten und UI-Hilfsfunktionen.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate

from logic import COLOR_POSITIVE, COLOR_NEGATIVE

# Standard-Markierungsfarbe für Bereitschafts-Tage in der Kalender-Heatmap.
# Wird überschrieben durch ``settings["bereitschaft_color"]`` (siehe Einstellungen).
COLOR_BEREITSCHAFT = "#eab308"  # Kräftiges Gelb, gut sichtbar in Light/Dark Mode


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
    Delegate für die Kalender-Heatmap.

    Zeichnet zusätzlich zur Standardzelle:
    - einen blauen Rahmen um den heutigen Tag
    - einen violetten Balken im unteren Viertel, wenn an dem Tag eine
      Bereitschaft eingetragen ist
    """

    # Custom data roles: jenseits der eingebauten Rollen, um Konflikte
    # mit ItemDataRole-Werten zu vermeiden.
    IS_TODAY_ROLE = Qt.ItemDataRole.UserRole + 1
    HAS_BEREITSCHAFT_ROLE = Qt.ItemDataRole.UserRole + 2
    CONNECT_LEFT_ROLE = Qt.ItemDataRole.UserRole + 3
    CONNECT_RIGHT_ROLE = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None, settings=None):
        """Initialisiert den Delegate.

        Args:
            parent:   QObject-Parent (typischerweise das QTableWidget).
            settings: Optionale Referenz auf das Settings-Dict; ermöglicht das
                      Auslesen der konfigurierten Bereitschaftsfarbe zur Laufzeit.
        """
        super().__init__(parent)
        self.settings = settings if settings is not None else {}

    def paint(self, painter: QPainter, option, index):
        """
        Zeichnet die Zelle inkl. Heute-Rahmen und Bereitschafts-Balken.
        """
        super().paint(painter, option, index)

        has_bereitschaft = index.data(self.HAS_BEREITSCHAFT_ROLE)
        if has_bereitschaft:
            self._draw_bereitschaft_bar(
                painter,
                option.rect,
                bool(index.data(self.CONNECT_LEFT_ROLE)),
                bool(index.data(self.CONNECT_RIGHT_ROLE)),
            )

        is_today = index.data(self.IS_TODAY_ROLE)
        if is_today:
            painter.setPen(QPen(QColor("#60a5fa"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = option.rect
            painter.drawRect(r.x() + 1, r.y() + 1, r.width() - 2, r.height() - 2)

    def _draw_bereitschaft_bar(self, painter: QPainter, rect,
                               connect_left: bool, connect_right: bool):
        """Zeichnet einen violetten Balken im unteren Viertel der Zelle.

        ``connect_left``/``connect_right`` steuern, ob der Balken bis an die
        jeweilige Zellkante reicht (für eine über mehrere Tage durchgehende
        Linie). Liegt kein Nachbar an, wird der Rand abgerundet.
        """
        painter.save()
        bar_height = max(4, rect.height() // 12)
        margin_x = 6
        bar_y = rect.bottom() - bar_height - 12

        # Linke/rechte Seite je nach Nachbar bis an die Zellkante ziehen.
        # +1 sorgt für ein nahtloses Überlappen mit dem nächsten Cell-Paint,
        # damit subpixel-Rundungen keine Lücke erzeugen.
        if connect_left:
            bar_x = rect.x()
            bar_w_left_extra = 1
        else:
            bar_x = rect.x() + margin_x
            bar_w_left_extra = 0
        if connect_right:
            bar_right = rect.x() + rect.width() + 1
        else:
            bar_right = rect.x() + rect.width() - margin_x
        bar_w = bar_right - bar_x + bar_w_left_extra

        color_hex = self.settings.get("bereitschaft_color") or COLOR_BEREITSCHAFT
        color = QColor(color_hex)
        if not color.isValid():
            color = QColor(COLOR_BEREITSCHAFT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = 0 if (connect_left or connect_right) else 2
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_height, radius, radius)
        painter.restore()
