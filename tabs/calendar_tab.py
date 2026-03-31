"""
Eigenständiges Widget für den Kalender-Heatmap-Tab.
"""
import calendar
from PyQt6.QtCore import QDate, QLocale, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QTableWidget, QHeaderView, QTableWidgetItem, QWidget
)

from i18n import get_locale, tr

from logic import get_holidays, format_time
from ui_components import HeatmapDelegate, overtime_qcolor, set_overtime_color


# pylint: disable=too-many-instance-attributes
class CalendarTab(QWidget):
    """Zeigt eine Kalender-Heatmap des aktuellen Monats mit Überstunden-Farbkodierung."""

    filter_changed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        """
        Initialisiert das Kalender-Widget.

        Args:
            settings: Einstellungs-Dictionary (gemeinsame Referenz).
            parent:   Eltern-Widget.
        """
        super().__init__(parent)
        self.settings = settings
        self.entries = []

        self._build_ui()

    def _build_ui(self):
        """Erstellt das Layout des Kalender-Tabs."""
        layout = QVBoxLayout(self)

        cal_toolbar = QHBoxLayout()
        self.btn_cal_prev = QPushButton(tr("< Vorheriger"))
        self.btn_cal_prev.clicked.connect(self._go_prev_month)
        self.btn_cal_next = QPushButton(tr("Nächster >"))
        self.btn_cal_next.clicked.connect(self._go_next_month)

        self.cal_month_filter = QComboBox()
        self.cal_month_filter.currentIndexChanged.connect(self._on_filter_changed)

        cal_toolbar.addWidget(QLabel(tr("Monat:")))
        cal_toolbar.addWidget(self.btn_cal_prev)
        cal_toolbar.addWidget(self.cal_month_filter)
        cal_toolbar.addWidget(self.btn_cal_next)
        cal_toolbar.addStretch()

        self.lbl_cal_month_sum = QLabel(tr("Monats-Saldo: {s}").format(s="0h 0m"))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_cal_month_sum.setFont(font)
        cal_toolbar.addWidget(self.lbl_cal_month_sum)
        layout.addLayout(cal_toolbar)

        self.cal_table = QTableWidget(6, 7)
        self.cal_table.setHorizontalHeaderLabels([
            get_locale().dayName(i, QLocale.FormatType.LongFormat) for i in range(1, 8)
        ])
        self.cal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cal_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cal_table.verticalHeader().hide()
        self.cal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cal_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.heatmap_delegate = HeatmapDelegate(self.cal_table)
        self.cal_table.setItemDelegate(self.heatmap_delegate)
        layout.addWidget(self.cal_table)

    def refresh(self, entries):
        """Aktualisiert die Einträge und zeichnet die Heatmap neu.

        Args:
            entries: Aktuelle Liste aller WorkEntry-Objekte.
        """
        self.entries = entries
        self._update_heatmap()

    def set_filter(self, month_str):
        """Setzt den Monatsfilter ohne das filter_changed-Signal auszulösen.

        Args:
            month_str: Monatsstring im Format 'yyyy-MM'.
        """
        idx = self.cal_month_filter.findData(month_str)
        if idx >= 0:
            self.cal_month_filter.blockSignals(True)
            self.cal_month_filter.setCurrentIndex(idx)
            self.cal_month_filter.blockSignals(False)
            self._update_heatmap()

    def _go_prev_month(self):
        """Navigiert einen Monat zurück."""
        idx = self.cal_month_filter.currentIndex()
        if idx < self.cal_month_filter.count() - 1:
            self.cal_month_filter.setCurrentIndex(idx + 1)

    def _go_next_month(self):
        """Navigiert einen Monat vor."""
        idx = self.cal_month_filter.currentIndex()
        if idx > 0:
            self.cal_month_filter.setCurrentIndex(idx - 1)

    def _on_filter_changed(self):
        """Wird aufgerufen, wenn der Benutzer den Monat im Dropdown ändert."""
        cal_val = self.cal_month_filter.currentData()
        if cal_val:
            self.filter_changed.emit(cal_val)
        self._update_heatmap()

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _update_heatmap(self):
        """Aktualisiert die Kalender-Heatmap für den ausgewählten Monat."""
        self.cal_month_filter.blockSignals(True)
        current_cal_filter = self.cal_month_filter.currentData()
        self.cal_month_filter.clear()

        months_set = set(e.date[:7] for e in self.entries if len(e.date) >= 7)
        today = QDate.currentDate()
        for i in range(-60, 61):
            months_set.add(today.addMonths(i).toString("yyyy-MM"))

        months = sorted(list(months_set), reverse=True)
        for m in months:
            self.cal_month_filter.addItem(f"{m[-2:]}/{m[:4]}", m)

        idx = self.cal_month_filter.findData(current_cal_filter)
        if idx < 0:
            idx = self.cal_month_filter.findData(today.toString("yyyy-MM"))
        if idx >= 0:
            self.cal_month_filter.setCurrentIndex(idx)

        self.btn_cal_prev.setEnabled(
            self.cal_month_filter.currentIndex() < self.cal_month_filter.count() - 1
        )
        self.btn_cal_next.setEnabled(self.cal_month_filter.currentIndex() > 0)
        self.cal_month_filter.blockSignals(False)

        sel_date_str = self.cal_month_filter.currentData()
        if not sel_date_str:
            sel_date_str = today.toString("yyyy-MM")

        year, month = map(int, sel_date_str.split('-'))
        cal = calendar.monthcalendar(year, month)

        country = self.settings.get("country", "DE")
        subdiv = self.settings.get("state")
        holidays = get_holidays(year, country, subdiv)

        day_mins = {}
        monthly_sum = 0
        for e in self.entries:
            if e.date.startswith(sel_date_str):
                day_mins[e.date] = day_mins.get(e.date, 0) + e.minutes
                monthly_sum += e.minutes

        self.lbl_cal_month_sum.setText(
            tr("Monats-Saldo: {s}").format(s=format_time(monthly_sum, show_plus=True))
        )
        set_overtime_color(self.lbl_cal_month_sum, monthly_sum)

        self.cal_table.setRowCount(len(cal))
        is_dark = self.settings.get("dark_mode", False)
        workdays_setting = self.settings.get("workdays", [0, 1, 2, 3, 4])

        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                item = self._make_cell(
                    day, col, year, month, today, day_mins, holidays, is_dark, workdays_setting
                )
                self.cal_table.setItem(row, col, item)

    # pylint: disable=too-many-positional-arguments,too-many-arguments
    def _make_cell(self, day, col, year, month, today,
                   day_mins, holidays, is_dark, workdays_setting):
        """Erstellt ein QTableWidgetItem für eine Kalender-Zelle."""
        if day == 0:
            item = QTableWidgetItem("")
            item.setData(Qt.ItemDataRole.UserRole + 1, False)
            item.setBackground(QColor("#222222" if is_dark else "#f3f4f6"))
            return item

        date_str = f"{year}-{month:02d}-{day:02d}"
        mins = day_mins.get(date_str, 0)
        is_holiday = date_str in holidays
        is_workday = col in workdays_setting

        f_mins = f"\n({format_time(mins, show_plus=True)})" if mins != 0 else ""
        text = f"{day}\n{holidays[date_str]}{f_mins}" if is_holiday else f"{day}{f_mins}"

        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_holiday:
            item.setToolTip(holidays[date_str])
            if mins == 0:
                item.setBackground(QColor("#1e3a8a" if is_dark else "#bfdbfe"))
                item.setForeground(QColor("#60a5fa" if is_dark else "#1d4ed8"))
            else:
                item.setBackground(overtime_qcolor(mins))
        elif mins == 0:
            if not is_workday:
                item.setBackground(QColor("#2d3748" if is_dark else "#e5e7eb"))
            else:
                item.setBackground(QColor("#333333" if is_dark else "#ffffff"))
        else:
            item.setBackground(overtime_qcolor(mins))

        is_today = year == today.year() and month == today.month() and day == today.day()
        item.setData(Qt.ItemDataRole.UserRole + 1, is_today)
        return item
