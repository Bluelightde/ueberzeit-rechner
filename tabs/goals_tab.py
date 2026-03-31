"""
Modul für die Tabs der Anwendung.
"""
import math
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QGroupBox, QHBoxLayout, QCheckBox,
    QLabel, QDateEdit, QSpinBox, QProgressBar, QGridLayout
)


class GoalsTabMixin:
    """Mixin for the goals and dashboard tab."""

    # pylint: disable=too-many-local-variables, too-many-statements, too-many-branches, too-many-nested-blocks
    def setup_goals_tab(self):
        """Erstellt den Tab für Ziele und das Fortschritts-Dashboard."""
        layout = QVBoxLayout(self.tab_goals)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 1. Konfigurations-Bereich
        settings_group = QGroupBox("Zeitraum und Überstunden-Ziel konfigurieren")
        settings_layout = QVBoxLayout(settings_group)

        goal_header_layout = QHBoxLayout()
        self.goal_active_cb = QCheckBox("Gleitzeit-Ziel aktivieren (Urlaubs-Sparer)")
        self.goal_active_cb.setChecked(self.settings.get("goal_active", False))
        self.goal_active_cb.stateChanged.connect(self.on_goal_changed)
        goal_header_layout.addWidget(self.goal_active_cb)
        goal_header_layout.addStretch()
        settings_layout.addLayout(goal_header_layout)

        goal_inputs_layout = QHBoxLayout()

        goal_inputs_layout.addWidget(QLabel("Urlaub / Frei von:"))
        self.goal_start_edit = QDateEdit()
        self.goal_start_edit.setCalendarPopup(True)
        self.goal_start_edit.setDate(
            QDate.fromString(self.settings.get("goal_start_date", ""), "yyyy-MM-dd")
        )
        self.goal_start_edit.dateChanged.connect(self.auto_calculate_goal_hours)
        goal_inputs_layout.addWidget(self.goal_start_edit)

        goal_inputs_layout.addWidget(QLabel("bis:"))
        self.goal_end_edit = QDateEdit()
        self.goal_end_edit.setCalendarPopup(True)
        self.goal_end_edit.setDate(
            QDate.fromString(self.settings.get("goal_end_date", ""), "yyyy-MM-dd")
        )
        self.goal_end_edit.dateChanged.connect(self.auto_calculate_goal_hours)
        goal_inputs_layout.addWidget(self.goal_end_edit)

        goal_inputs_layout.addWidget(QLabel(" | Benötigte Überstunden:"))
        self.goal_hours_spin = QSpinBox()
        self.goal_hours_spin.setRange(0, 5000)
        self.goal_hours_spin.setValue(self.settings.get("goal_hours", 0))
        self.goal_hours_spin.setSuffix(" h")
        self.goal_hours_spin.valueChanged.connect(self.on_goal_changed)
        goal_inputs_layout.addWidget(self.goal_hours_spin)

        goal_inputs_layout.addStretch()
        settings_layout.addLayout(goal_inputs_layout)

        layout.addWidget(settings_group)

        # 2. Dashboard-Bereich
        self.dashboard_group = QGroupBox("Fortschritts-Dashboard")
        dashboard_layout = QVBoxLayout(self.dashboard_group)

        self.goal_progress_bar = QProgressBar()
        self.goal_progress_bar.setRange(0, 100)
        self.goal_progress_bar.setValue(0)
        self.goal_progress_bar.setFixedHeight(30)
        self.goal_progress_bar.setTextVisible(True)
        self.goal_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dashboard_layout.addWidget(self.goal_progress_bar)

        grid = QGridLayout()
        grid.setSpacing(15)

        # Kachel: Aktueller Stand
        self.lbl_goal_current = QLabel("0h 0m")
        self.lbl_goal_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_goal_current.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        grid.addWidget(QLabel("Aktueller Stand", alignment=Qt.AlignmentFlag.AlignCenter), 0, 0)
        grid.addWidget(self.lbl_goal_current, 1, 0)

        # Kachel: Es fehlen noch
        self.lbl_goal_missing = QLabel("0h 0m")
        self.lbl_goal_missing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_goal_missing.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        grid.addWidget(QLabel("Es fehlen noch", alignment=Qt.AlignmentFlag.AlignCenter), 0, 1)
        grid.addWidget(self.lbl_goal_missing, 1, 1)

        # Kachel: Verbleibende Tage (bis zum Start des Zeitraums)
        self.lbl_goal_days = QLabel("0")
        self.lbl_goal_days.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_goal_days.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        grid.addWidget(
            QLabel("Arbeitstage zum Ansparen", alignment=Qt.AlignmentFlag.AlignCenter), 0, 2
        )
        grid.addWidget(self.lbl_goal_days, 1, 2)

        dashboard_layout.addLayout(grid)

        # Fazit-Label unten
        self.lbl_goal_action = QLabel("-")
        self.lbl_goal_action.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_goal_action.setFont(QFont("Arial", 12))
        dashboard_layout.addSpacing(15)
        dashboard_layout.addWidget(self.lbl_goal_action)

        layout.addWidget(self.dashboard_group)
        layout.addStretch()

        if self.settings.get("goal_hours", 0) == 0:
            self.auto_calculate_goal_hours()

    def auto_calculate_goal_hours(self):
        """Berechnet die benötigten Überstunden automatisch anhand des gewählten Zeitraums."""
        start_d = self.goal_start_edit.date()
        end_d = self.goal_end_edit.date()
        if start_d > end_d:
            return

        total_target_mins = 0
        curr = start_d

        while curr <= end_d:
            total_target_mins += self.get_target_minutes_for_date(curr.toString("yyyy-MM-dd"))
            curr = curr.addDays(1)

        total_hours_needed = total_target_mins / 60.0

        self.goal_hours_spin.blockSignals(True)
        self.goal_hours_spin.setValue(math.ceil(total_hours_needed))
        self.goal_hours_spin.blockSignals(False)

        self.on_goal_changed()

    def on_goal_changed(self):
        """Wird aufgerufen, wenn sich die Ziel-Einstellungen ändern."""
        self.settings["goal_active"] = self.goal_active_cb.isChecked()
        self.settings["goal_start_date"] = self.goal_start_edit.date().toString("yyyy-MM-dd")
        self.settings["goal_end_date"] = self.goal_end_edit.date().toString("yyyy-MM-dd")
        self.settings["goal_hours"] = self.goal_hours_spin.value()
        self.save_settings()

        self.goal_start_edit.setEnabled(self.goal_active_cb.isChecked())
        self.goal_end_edit.setEnabled(self.goal_active_cb.isChecked())
        self.goal_hours_spin.setEnabled(self.goal_active_cb.isChecked())
        self.dashboard_group.setVisible(self.goal_active_cb.isChecked())

        if self.goal_active_cb.isChecked():
            self.update_goal_status()

    # pylint: disable=too-many-local-variables, too-many-statements, too-many-branches, too-many-nested-blocks
    def update_goal_status(self):
        """Aktualisiert die Anzeige des Fortschritts-Dashboards."""
        if not self.goal_active_cb.isChecked():
            return

        target_start_date = self.goal_start_edit.date()
        target_mins = self.goal_hours_spin.value() * 60
        current_saldo = sum(e.minutes for e in self.entries)

        progress_saldo = max(0, current_saldo)

        if target_mins == 0:
            percentage = 100
        else:
            percentage = min(100, int((progress_saldo / target_mins) * 100))

        self.goal_progress_bar.setValue(percentage)
        self.goal_progress_bar.setFormat(f"{percentage}% erreicht")
        self.lbl_goal_current.setText(self.format_time(current_saldo))

        missing_mins = target_mins - current_saldo

        if missing_mins <= 0:
            self.lbl_goal_missing.setText("0h 0m")
            self.lbl_goal_days.setText("-")
            self.lbl_goal_action.setText(
                "🎉 Herzlichen Glückwunsch! Du hast genug Überstunden für diesen Zeitraum angespart!"
            )
            self.lbl_goal_action.setStyleSheet("color: #10b981; font-weight: bold;")
            return

        self.lbl_goal_missing.setText(self.format_time(missing_mins))

        today = QDate.currentDate()
        if target_start_date <= today:
            self.lbl_goal_days.setText("0")
            self.lbl_goal_action.setText(
                "⚠️ Der gewünschte Zeitraum hat bereits begonnen oder ist heute!"
            )
            self.lbl_goal_action.setStyleSheet("color: #ef4444; font-weight: bold;")
            return

        workdays = 0
        curr = today.addDays(1)

        while curr < target_start_date:
            if self.get_target_minutes_for_date(curr.toString("yyyy-MM-dd")) > 0:
                workdays += 1
            curr = curr.addDays(1)

        self.lbl_goal_days.setText(str(workdays))

        if workdays == 0:
            self.lbl_goal_action.setText("Keine regulären Arbeitstage mehr zum Ansparen übrig!")
            self.lbl_goal_action.setStyleSheet("color: #ef4444;")
        else:
            extra_per_day = missing_mins / workdays
            self.lbl_goal_action.setText(
                f"Tipp: Wenn du ab sofort jeden Tag "
                f"<b>{int(extra_per_day)} Minuten</b> länger machst, "
                "erreichst du dein Ziel punktgenau."
            )
            self.lbl_goal_action.setStyleSheet("color: #3b82f6;")
