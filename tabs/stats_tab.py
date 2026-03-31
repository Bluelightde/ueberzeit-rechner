"""
Eigenständiges Widget für den Diagramm- und Statistik-Tab.
"""
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class StatsTab(QWidget):
    """Zeigt ein monatliches Balkendiagramm der Überstunden."""

    def __init__(self, settings, parent=None):
        """
        Initialisiert das Statistik-Widget.

        Args:
            settings: Einstellungs-Dictionary (gemeinsame Referenz mit Hauptfenster).
            parent:   Eltern-Widget.
        """
        super().__init__(parent)
        self.settings = settings
        self.entries = []

        layout = QVBoxLayout(self)
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

    def refresh(self, entries):
        """Aktualisiert die Einträge und zeichnet das Diagramm neu.

        Args:
            entries: Aktuelle Liste aller WorkEntry-Objekte.
        """
        self.entries = entries
        self._update_chart()

    def _update_chart(self):
        """Zeichnet das monatliche Balkendiagramm der Überstunden neu."""
        monthly_totals = {}
        for e in reversed(self.entries):
            if len(e.date) >= 7:
                m = e.date[:7]
                monthly_totals[m] = monthly_totals.get(m, 0) + e.minutes

        self.figure.clear()
        is_dark = self.settings.get("dark_mode", False)
        bg_color = '#31363b' if is_dark else '#ffffff'
        text_color = '#e0e0e0' if is_dark else '#000000'

        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=text_color)
        for spine in ax.spines.values():
            spine.set_edgecolor(text_color)

        if not monthly_totals:
            ax.text(0.5, 0.5, "Keine Daten vorhanden",
                    color=text_color, ha='center', va='center')
        else:
            months = list(monthly_totals.keys())
            values = [v / 60 for v in monthly_totals.values()]
            colors = ['#10b981' if v >= 0 else '#ef4444' for v in values]
            ax.bar(months, values, color=colors)
            ax.set_ylabel("Überstunden (in Stunden)", color=text_color)
            ax.set_title("Monatlicher Überstunden-Verlauf", color=text_color)
            self.figure.autofmt_xdate()

        self.canvas.draw()
