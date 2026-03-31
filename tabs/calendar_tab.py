"""
Modul für die Tabs der Anwendung.
"""
import calendar
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QTableWidget, QHeaderView, QTableWidgetItem
)

from logic import get_holidays
from ui_components import HeatmapDelegate


class CalendarTabMixin:
    """Mixin for the calendar heatmap tab."""

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches, too-many-nested-blocks
    def setup_calendar_tab(self):
        """Erstellt den Tab für die Kalender-Heatmap."""
        layout = QVBoxLayout(self.tab_calendar)

        cal_toolbar = QHBoxLayout()

        self.btn_cal_prev = QPushButton("< Vorheriger")
        self.btn_cal_prev.clicked.connect(self.cal_go_prev_month)
        self.btn_cal_next = QPushButton("Nächster >")
        self.btn_cal_next.clicked.connect(self.cal_go_next_month)

        self.cal_month_filter = QComboBox()
        self.cal_month_filter.currentIndexChanged.connect(self.on_cal_filter_changed)

        cal_toolbar.addWidget(QLabel("Monat:"))
        cal_toolbar.addWidget(self.btn_cal_prev)
        cal_toolbar.addWidget(self.cal_month_filter)
        cal_toolbar.addWidget(self.btn_cal_next)

        cal_toolbar.addStretch()

        self.lbl_cal_month_sum = QLabel("Monats-Saldo: 0h 0m")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_cal_month_sum.setFont(font)
        cal_toolbar.addWidget(self.lbl_cal_month_sum)

        layout.addLayout(cal_toolbar)

        self.cal_table = QTableWidget(6, 7)

        self.cal_table.setHorizontalHeaderLabels(
            ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        )
        self.cal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cal_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cal_table.verticalHeader().hide()
        self.cal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cal_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.heatmap_delegate = HeatmapDelegate(self.cal_table)
        self.cal_table.setItemDelegate(self.heatmap_delegate)
        layout.addWidget(self.cal_table)

    def cal_go_prev_month(self):
        """Navigiert im Kalender einen Monat zurück."""
        idx = self.cal_month_filter.currentIndex()
        if idx < self.cal_month_filter.count() - 1:
            self.cal_month_filter.setCurrentIndex(idx + 1)

    def cal_go_next_month(self):
        """Navigiert im Kalender einen Monat vor."""
        idx = self.cal_month_filter.currentIndex()
        if idx > 0:
            self.cal_month_filter.setCurrentIndex(idx - 1)

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches, too-many-nested-blocks
    def update_calendar_heatmap(self):
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

        state = self.settings.get("state", "TH")
        holidays = get_holidays(year, state)

        day_mins = {}
        monthly_sum = 0

        for e in self.entries:
            if e.date.startswith(sel_date_str):
                day_mins[e.date] = day_mins.get(e.date, 0) + e.minutes
                monthly_sum += e.minutes

        self.lbl_cal_month_sum.setText(
            f"Monats-Saldo: {self.format_time(monthly_sum, show_plus=True)}"
        )
        if monthly_sum > 0:
            self.lbl_cal_month_sum.setStyleSheet("color: #10b981;")
        elif monthly_sum < 0:
            self.lbl_cal_month_sum.setStyleSheet("color: #ef4444;")
        else:
            self.lbl_cal_month_sum.setStyleSheet("")

        self.cal_table.setRowCount(len(cal))
        is_dark = self.settings.get("dark_mode", False)
        workdays_setting = self.settings.get("workdays", [0, 1, 2, 3, 4])

        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                if day == 0:
                    item = QTableWidgetItem("")
                    item.setData(Qt.ItemDataRole.UserRole + 1, False)
                    item.setBackground(QColor("#222222" if is_dark else "#f3f4f6"))
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    mins = day_mins.get(date_str, 0)
                    is_holiday = date_str in holidays
                    is_workday = col in workdays_setting

                    f_mins = f"\n({self.format_time(mins, show_plus=True)})" if mins != 0 else ""
                    if is_holiday:
                        hol_name = holidays[date_str]
                        text = f"{day}\n{hol_name}{f_mins}"
                    else:
                        text = f"{day}{f_mins}"

                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    if is_holiday:
                        item.setToolTip(holidays[date_str])
                        if mins == 0:
                            item.setBackground(QColor("#1e3a8a" if is_dark else "#bfdbfe"))
                            item.setForeground(QColor("#60a5fa" if is_dark else "#1d4ed8"))
                        elif mins > 0:
                            alpha = min(255, 60 + (mins * 2))
                            item.setBackground(QColor(16, 185, 129, alpha))
                        else:
                            alpha = min(255, 60 + (abs(mins) * 2))
                            item.setBackground(QColor(239, 68, 68, alpha))
                    else:
                        if mins == 0:
                            if not is_workday:
                                item.setBackground(QColor("#2d3748" if is_dark else "#e5e7eb"))
                            else:
                                item.setBackground(QColor("#333333" if is_dark else "#ffffff"))
                        elif mins > 0:
                            alpha = min(255, 60 + (mins * 2))
                            item.setBackground(QColor(16, 185, 129, alpha))
                        else:
                            alpha = min(255, 60 + (abs(mins) * 2))
                            item.setBackground(QColor(239, 68, 68, alpha))

                    # Den aktuellen Tag (Heute) prüfen und markieren
                    if year == today.year() and month == today.month() and day == today.day():
                        item.setData(Qt.ItemDataRole.UserRole + 1, True)
                    else:
                        item.setData(Qt.ItemDataRole.UserRole + 1, False)

                self.cal_table.setItem(row, col, item)

    def on_cal_filter_changed(self):
        """Wird aufgerufen, wenn der Monatsfilter im Kalender geändert wird."""
        cal_val = self.cal_month_filter.currentData()
        if cal_val:
            idx = self.month_filter.findData(cal_val)
            if idx >= 0:
                self.month_filter.blockSignals(True)
                self.month_filter.setCurrentIndex(idx)
                self.month_filter.blockSignals(False)
        self.update_calendar_heatmap()
