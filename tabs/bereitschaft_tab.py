"""
Eigenständiges Widget für den Bereitschafts-Tab.

Bereitschaft (On-Call) wird hier verwaltet: Eintragen, Bearbeiten, Löschen.
Die Daten beeinflussen weder Pausen- noch Überstunden-Berechnung und
erscheinen lediglich als violetter Balken im Kalender-Tab.
"""
import logging

from PyQt6.QtCore import QDate, QLocale, Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTimeEdit,
    QVBoxLayout, QWidget,
)

from i18n import get_locale, tr
from logic import fmt_date
from models import BereitschaftEntry

logger = logging.getLogger(__name__)


def _short_time_format() -> str:
    """Gibt das kurze Zeit-Format der aktuellen Locale zurück."""
    return get_locale().timeFormat(QLocale.FormatType.ShortFormat)


# pylint: disable=too-few-public-methods
class BereitschaftDialog(QDialog):
    """Dialog zum Anlegen oder Bearbeiten eines Bereitschafts-Eintrags."""

    def __init__(self, entry: BereitschaftEntry, parent=None):
        """Initialisiert den Dialog mit den Werten des übergebenen Eintrags."""
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle(tr("Bereitschaft bearbeiten"))

        layout = QFormLayout(self)

        _date_fmt = get_locale().dateFormat(QLocale.FormatType.ShortFormat)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(_date_fmt)
        self.date_edit.setDate(QDate.fromString(entry.date, "yyyy-MM-dd"))
        layout.addRow(QLabel(tr("Datum:")), self.date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat(_date_fmt)
        end_str = entry.effective_end_date
        self.end_date_edit.setDate(QDate.fromString(end_str, "yyyy-MM-dd"))
        layout.addRow(QLabel(tr("Bis:")), self.end_date_edit)

        # Wenn das Start-Datum verschoben wird, soll das Ende mitwandern, sofern
        # es vorher gleich oder vor dem neuen Start lag.
        self.date_edit.dateChanged.connect(self._sync_end_with_start)

        self.use_times_cb = QCheckBox(tr("Mit Uhrzeiten"))
        layout.addRow(self.use_times_cb)

        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(_short_time_format())
        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat(_short_time_format())

        has_times = bool(entry.start or entry.end)
        self.use_times_cb.setChecked(has_times)
        self.time_start.setEnabled(has_times)
        self.time_end.setEnabled(has_times)
        if entry.start:
            self.time_start.setTime(QTime.fromString(entry.start, "HH:mm"))
        if entry.end:
            self.time_end.setTime(QTime.fromString(entry.end, "HH:mm"))
        self.use_times_cb.stateChanged.connect(self._toggle_times)

        layout.addRow(QLabel(tr("Start:")), self.time_start)
        layout.addRow(QLabel(tr("Ende:")), self.time_end)

        self.note_edit = QLineEdit(entry.note)
        self.note_edit.setPlaceholderText(tr("Notiz (optional)"))
        layout.addRow(QLabel(tr("Notiz:")), self.note_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _toggle_times(self):
        """Aktiviert/deaktiviert die Uhrzeit-Felder anhand der Checkbox."""
        enabled = self.use_times_cb.isChecked()
        self.time_start.setEnabled(enabled)
        self.time_end.setEnabled(enabled)

    def _sync_end_with_start(self, new_start: QDate):
        """Zieht das Bis-Datum mit, wenn es vor dem neuen Start liegt."""
        if self.end_date_edit.date() < new_start:
            self.end_date_edit.setDate(new_start)

    def apply_to_entry(self):
        """Schreibt die Dialog-Werte zurück in das Entry-Objekt."""
        start_date = self.date_edit.date()
        end_date = max(self.end_date_edit.date(), start_date)
        self.entry.date = start_date.toString("yyyy-MM-dd")
        self.entry.end_date = (
            "" if end_date == start_date else end_date.toString("yyyy-MM-dd")
        )
        if self.use_times_cb.isChecked():
            self.entry.start = self.time_start.time().toString("HH:mm")
            self.entry.end = self.time_end.time().toString("HH:mm")
        else:
            self.entry.start = ""
            self.entry.end = ""
        self.entry.note = self.note_edit.text().strip()


# pylint: disable=too-many-instance-attributes
class BereitschaftTab(QWidget):
    """Tab zur Verwaltung von Bereitschafts-Tagen (On-Call)."""

    data_changed = pyqtSignal()

    def __init__(self, db, parent=None):
        """Initialisiert den Bereitschafts-Tab.

        Args:
            db:     DBManager-Instanz für Datenbankzugriffe.
            parent: Eltern-Widget.
        """
        super().__init__(parent)
        self.db = db
        self.entries: list[BereitschaftEntry] = []

        self._build_ui()

    def set_db(self, db):
        """Tauscht die DB-Verbindung aus (z.B. bei Pfadänderung)."""
        self.db = db

    # --- UI ---

    # pylint: disable=too-many-statements
    def _build_ui(self):
        """Erstellt das Layout des Bereitschafts-Tabs."""
        layout = QVBoxLayout(self)

        frame_input = QFrame()
        frame_layout = QVBoxLayout(frame_input)

        row = QHBoxLayout()
        _date_fmt = get_locale().dateFormat(QLocale.FormatType.ShortFormat)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(_date_fmt)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._sync_end_with_start)
        row.addWidget(QLabel(tr("Datum:")))
        row.addWidget(self.date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat(_date_fmt)
        self.end_date_edit.setDate(QDate.currentDate())
        row.addWidget(QLabel(tr("Bis:")))
        row.addWidget(self.end_date_edit)

        self.use_times_cb = QCheckBox(tr("Mit Uhrzeiten"))
        self.use_times_cb.stateChanged.connect(self._toggle_times)
        row.addWidget(self.use_times_cb)

        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(_short_time_format())
        self.time_start.setTime(QTime(18, 0))
        self.time_start.setEnabled(False)
        row.addWidget(QLabel(tr("Start:")))
        row.addWidget(self.time_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat(_short_time_format())
        self.time_end.setTime(QTime(6, 0))
        self.time_end.setEnabled(False)
        row.addWidget(QLabel(tr("Ende:")))
        row.addWidget(self.time_end)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText(tr("Notiz (optional)"))
        row.addWidget(QLabel(tr("Notiz:")))
        row.addWidget(self.note_edit)

        btn_add = QPushButton(tr("Eintragen"))
        btn_add.clicked.connect(self.add_entry)
        row.addWidget(btn_add)

        frame_layout.addLayout(row)
        layout.addWidget(frame_input)

        toolbar = QHBoxLayout()
        self.month_filter = QComboBox()
        self.month_filter.addItem(tr("Alle"), "ALL")
        self.month_filter.currentIndexChanged.connect(self._refresh_table)
        toolbar.addWidget(QLabel(tr("Filter:")))
        toolbar.addWidget(self.month_filter)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("Zeitraum"), tr("Uhrzeit"), tr("Notiz"), tr("Aktion")
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    def _toggle_times(self):
        """Aktiviert/deaktiviert die Uhrzeit-Felder im Eingabe-Bereich."""
        enabled = self.use_times_cb.isChecked()
        self.time_start.setEnabled(enabled)
        self.time_end.setEnabled(enabled)

    def _sync_end_with_start(self, new_start: QDate):
        """Hält das Bis-Datum >= dem Start-Datum."""
        if self.end_date_edit.date() < new_start:
            self.end_date_edit.setDate(new_start)

    # --- Daten ---

    def refresh(self, entries):
        """Lädt eine neue Liste von Bereitschafts-Einträgen.

        Args:
            entries: Liste aller BereitschaftEntry-Objekte.
        """
        self.entries = entries
        self._update_month_filter()
        self._refresh_table()

    def add_entry(self):
        """Erstellt einen neuen Bereitschafts-Eintrag aus den Eingabefeldern."""
        start_qd = self.date_edit.date()
        end_qd = max(self.end_date_edit.date(), start_qd)
        date_str = start_qd.toString("yyyy-MM-dd")
        end_date_str = "" if end_qd == start_qd else end_qd.toString("yyyy-MM-dd")

        if self.use_times_cb.isChecked():
            start_str = self.time_start.time().toString("HH:mm")
            end_str = self.time_end.time().toString("HH:mm")
        else:
            start_str = ""
            end_str = ""

        entry = BereitschaftEntry(
            id=0,
            date=date_str,
            start=start_str,
            end=end_str,
            note=self.note_edit.text().strip(),
            end_date=end_date_str,
        )
        self.db.insert_bereitschaft(entry)
        self.note_edit.clear()
        self.data_changed.emit()

    def _edit_entry(self, entry: BereitschaftEntry):
        """Öffnet den Edit-Dialog für einen bestehenden Eintrag."""
        dialog = BereitschaftDialog(entry, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply_to_entry()
            self.db.update_bereitschaft(entry)
            self.data_changed.emit()

    def _delete_entry(self, entry: BereitschaftEntry):
        """Löscht einen Bereitschafts-Eintrag nach Bestätigung."""
        reply = QMessageBox.question(
            self, tr("Löschen bestätigen"),
            tr("Bereitschaft vom {d} wirklich löschen?").format(
                d=fmt_date(entry.date)
            ),
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_bereitschaft(entry.id)
            self.data_changed.emit()

    def _on_double_click(self, row, _column):
        """Öffnet beim Doppelklick auf eine Zeile den Edit-Dialog."""
        if 0 <= row < self.table.rowCount():
            entry = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if entry is not None:
                self._edit_entry(entry)

    # --- Tabelle / Filter ---

    def _update_month_filter(self):
        """Aktualisiert die Monatsfilter-Dropdown-Einträge."""
        current = self.month_filter.currentData()
        self.month_filter.blockSignals(True)
        self.month_filter.clear()
        self.month_filter.addItem(tr("Alle"), "ALL")

        months = sorted({e.date[:7] for e in self.entries if len(e.date) >= 7}, reverse=True)
        for m in months:
            self.month_filter.addItem(f"{m[-2:]}/{m[:4]}", m)

        idx = self.month_filter.findData(current)
        self.month_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.month_filter.blockSignals(False)

    def _refresh_table(self):
        """Zeichnet die Tabelle gemäß aktuellem Monatsfilter neu."""
        selected = self.month_filter.currentData() or "ALL"
        if selected == "ALL":
            visible = list(self.entries)
        else:
            visible = [e for e in self.entries if e.date.startswith(selected)]

        self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            self._fill_row(row, entry)

    def _fill_row(self, row: int, entry: BereitschaftEntry):
        """Füllt eine Tabellenzeile mit den Werten eines Eintrags."""
        if entry.effective_end_date != entry.date:
            period_text = f"{fmt_date(entry.date)} – {fmt_date(entry.effective_end_date)}"
        else:
            period_text = fmt_date(entry.date)
        period_item = QTableWidgetItem(period_text)
        period_item.setData(Qt.ItemDataRole.UserRole, entry)
        self.table.setItem(row, 0, period_item)

        if entry.start or entry.end:
            time_text = f"{entry.start or '—'} – {entry.end or '—'}"
        else:
            time_text = tr("ganztägig")
        self.table.setItem(row, 1, QTableWidgetItem(time_text))

        self.table.setItem(row, 2, QTableWidgetItem(entry.note))

        btn_style = "padding: 2px 8px; min-height: 24px;"
        btn_edit = QPushButton(tr("Bearbeiten"))
        btn_edit.setStyleSheet(btn_style)
        btn_edit.clicked.connect(lambda _, e=entry: self._edit_entry(e))
        btn_del = QPushButton(tr("Löschen"))
        btn_del.setStyleSheet(btn_style)
        btn_del.clicked.connect(lambda _, e=entry: self._delete_entry(e))

        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 3, 4, 3)
        action_layout.setSpacing(4)
        action_layout.addWidget(btn_edit)
        action_layout.addWidget(btn_del)
        self.table.setCellWidget(row, 3, action_widget)
