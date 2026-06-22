"""
Eigenständiges Widget für den Anwesenheits-Tab.

Hier wird die Login-/Logout-Historie der vergangenen Tage angezeigt.
Die Daten werden beim Start der App (Login) und beim Schließen (Logout)
automatisch aufgezeichnet – ohne dass ein Arbeitseintrag entsteht.
So kann man vergessene Einträge später anhand der Anwesenheitszeiten
nachholen.
"""
import logging
from PyQt6.QtCore import QTime

from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from i18n import tr
from logic import fmt_date

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class SessionTab(QWidget):
    """Tab zur Anzeige der Login-/Logout-Historie (Anwesenheit)."""

    def __init__(self, db, parent=None):
        """Initialisiert den Anwesenheits-Tab.

        Args:
            db:     DBManager-Instanz für Datenbankzugriffe.
            parent: Eltern-Widget.
        """
        super().__init__(parent)
        self.db = db
        self.sessions: list[dict] = []

        self._build_ui()

    def set_db(self, db):
        """Tauscht die DB-Verbindung aus (z.B. bei Pfadänderung)."""
        self.db = db

    # --- UI ---

    def _build_ui(self):
        """Erstellt das Layout des Anwesenheits-Tabs."""
        layout = QVBoxLayout(self)

        info = QLabel(tr(
            "Hier werden deine Login- und Logout-Zeiten aus den "
            "System-Protokollen ausgelesen – die App muss dafür nicht "
            "laufen. Die Zeiten dienen als Gedächtnisstütze, es wird "
            "kein Arbeitseintrag erstellt. Du kannst vergessene Einträge "
            "anhand dieser Übersicht später nachholen."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; padding: 8px;")
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        self.month_filter = QComboBox()
        self.month_filter.addItem(tr("Alle"), "ALL")
        self.month_filter.currentIndexChanged.connect(self._refresh_table)
        toolbar.addWidget(QLabel(tr("Filter:")))
        toolbar.addWidget(self.month_filter)
        toolbar.addStretch()
        btn_refresh = QPushButton(tr("Aktualisieren"))
        btn_refresh.clicked.connect(self.refresh_from_db)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("Datum"), tr("Login"), tr("Logout"), tr("Anwesend")
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    # --- Daten ---

    def refresh(self, sessions):
        """Lädt eine neue Liste von Anwesenheits-Einträgen.

        Args:
            sessions: Liste von Dicts mit 'date', 'start', 'end'.
        """
        self.sessions = sessions
        self._update_month_filter()
        self._refresh_table()

    def refresh_from_db(self):
        """Lädt die Anwesenheits-Daten direkt aus der Datenbank."""
        self.sessions = self.db.load_all_device_logins()
        self._update_month_filter()
        self._refresh_table()

    # --- Tabelle / Filter ---

    def _update_month_filter(self):
        """Aktualisiert die Monatsfilter-Dropdown-Einträge."""
        current = self.month_filter.currentData()
        self.month_filter.blockSignals(True)
        self.month_filter.clear()
        self.month_filter.addItem(tr("Alle"), "ALL")

        months = sorted(
            {s["date"][:7] for s in self.sessions if len(s["date"]) >= 7},
            reverse=True,
        )
        for m in months:
            self.month_filter.addItem(f"{m[-2:]}/{m[:4]}", m)

        idx = self.month_filter.findData(current)
        self.month_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.month_filter.blockSignals(False)

    def _refresh_table(self):
        """Zeichnet die Tabelle gemäß aktuellem Monatsfilter neu."""
        selected = self.month_filter.currentData() or "ALL"
        if selected == "ALL":
            visible = list(self.sessions)
        else:
            visible = [s for s in self.sessions if s["date"].startswith(selected)]

        self.table.setRowCount(len(visible))
        for row, session in enumerate(visible):
            self._fill_row(row, session)

    def _fill_row(self, row: int, session: dict):
        """Füllt eine Tabellenzeile mit Login/Logout/Anwesenheitsdauer."""
        date_item = QTableWidgetItem(fmt_date(session["date"]))
        self.table.setItem(row, 0, date_item)

        login_str = session["start"] or "—"
        logout_str = session["end"] or "—"
        self.table.setItem(row, 1, QTableWidgetItem(login_str))
        self.table.setItem(row, 2, QTableWidgetItem(logout_str))

        duration = self._compute_duration(session["start"], session["end"])
        self.table.setItem(row, 3, QTableWidgetItem(duration))

    @staticmethod
    def _compute_duration(start: str, end: str) -> str:
        """Berechnet die Anwesenheitsdauer aus Login/Logout (HH:mm).

        Gibt '—' zurück, wenn eine Zeit fehlt oder ungültig ist.
        Bei Logout am nächsten Tag (z.B. Nachtschicht) wird 24h addiert.
        """
        if not start or not end:
            return "—"
        t_start = QTime.fromString(start, "HH:mm")
        t_end = QTime.fromString(end, "HH:mm")
        if not t_start.isValid() or not t_end.isValid():
            return "—"
        start_mins = t_start.hour() * 60 + t_start.minute()
        end_mins = t_end.hour() * 60 + t_end.minute()
        diff = end_mins - start_mins
        if diff < 0:
            diff += 24 * 60  # Logout am Folgetag
        h = diff // 60
        m = diff % 60
        return f"{h}h {m}m"