
"""
Dialog-Fenster für Einstellungen und zum Bearbeiten von Einträgen.
"""
from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog,
    QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTimeEdit, QVBoxLayout
)
from config import BUNDESLAENDER, DB_FILE
from models import WorkEntry
from logic import calculate_timed_entries

class SettingsDialog(QDialog):
    """
    Dialog zum Verwalten der Benutzereinstellungen wie Standardarbeitszeiten,
    Bundesland und Sonderarbeitstage.
    """
    def __init__(self, current_settings, parent=None):
        """
        Initialisiert den Einstellungsdialog mit den aktuellen Werten.
        """
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(380, 480)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Tages-Standardwerte:</b>"))

        self.login_time_cb = QCheckBox("Login-Zeit als Startzeit verwenden")
        self.login_time_cb.setToolTip(
            "Liest beim Programmstart die letzte Anmeldezeit des Benutzers aus.\n"
            "Die Standard-Startzeit dient als Fallback, falls die Anmeldezeit\n"
            "nicht ermittelt werden kann."
        )
        self.login_time_cb.setChecked(current_settings.get("use_login_time", False))
        layout.addWidget(self.login_time_cb)

        self._setup_workdays_ui(layout, current_settings)
        self._setup_time_settings_ui(layout, current_settings)

        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Pausen-Regelung:</b>"))
        self.auto_break_cb = QCheckBox("Automatische Pausen-Berechnung")
        self.auto_break_cb.setToolTip("6-9h: 30 Min, >9h: 45 Min")
        self.auto_break_cb.setChecked(current_settings.get("auto_break", True))
        layout.addWidget(self.auto_break_cb)

        self._setup_regional_ui(layout, current_settings)
        self._setup_special_days_ui(layout, current_settings)

        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Darstellung:</b>"))
        self.dark_mode_cb = QCheckBox("Dark Mode aktivieren")
        self.dark_mode_cb.setChecked(current_settings.get("dark_mode", False))
        layout.addWidget(self.dark_mode_cb)

        self.btn_save = QPushButton("Speichern")
        self.btn_save.clicked.connect(self.accept)

        self._setup_db_path_ui(layout, current_settings)

        layout.addSpacing(15)
        layout.addWidget(self.btn_save)

    def _setup_workdays_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Arbeitstage (Soll-Tage):</b>"))
        self.workday_checkboxes = []
        workdays_layout = QHBoxLayout()
        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        selected_workdays = current_settings.get("workdays", [0, 1, 2, 3, 4])
        for i, day_name in enumerate(days):
            cb = QCheckBox(day_name)
            cb.setChecked(i in selected_workdays)
            workdays_layout.addWidget(cb)
            self.workday_checkboxes.append(cb)
        layout.addLayout(workdays_layout)

    def _setup_time_settings_ui(self, layout, current_settings):
        layout.addSpacing(10)
        time_layout = QHBoxLayout()
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        default_start = current_settings.get("default_start", "07:00")
        self.time_start.setTime(QTime.fromString(default_start, "HH:mm"))
        self.time_start.setEnabled(not current_settings.get("use_login_time", False))
        self.login_time_cb.stateChanged.connect(self._on_login_time_state_changed)
        time_layout.addWidget(QLabel("Fallback Startzeit:"))
        time_layout.addWidget(self.time_start)
        layout.addLayout(time_layout)

        target_layout = QHBoxLayout()
        self.time_target = QTimeEdit()
        self.time_target.setDisplayFormat("HH:mm")
        target_work_time = current_settings.get("target_work_time", "08:00")
        self.time_target.setTime(QTime.fromString(target_work_time, "HH:mm"))
        target_layout.addWidget(QLabel("Regelarbeitszeit (Soll):"))
        target_layout.addWidget(self.time_target)
        layout.addLayout(target_layout)

        max_layout = QHBoxLayout()
        self.max_hours_spin = QSpinBox()
        self.max_hours_spin.setRange(6, 24)
        self.max_hours_spin.setSuffix(" h")
        self.max_hours_spin.setValue(current_settings.get("max_work_hours", 10))
        max_layout.addWidget(QLabel("Max. anrechenbare Arbeitszeit:"))
        max_layout.addWidget(self.max_hours_spin)
        layout.addLayout(max_layout)

    def _setup_regional_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Regionales:</b>"))
        state_layout = QHBoxLayout()
        self.state_combo = QComboBox()
        for code, name in BUNDESLAENDER.items():
            self.state_combo.addItem(name, code)
        curr_state = current_settings.get("state", "TH")
        idx = self.state_combo.findData(curr_state)
        if idx >= 0:
            self.state_combo.setCurrentIndex(idx)
        state_layout.addWidget(QLabel("Bundesland (für Feiertage):"))
        state_layout.addWidget(self.state_combo)
        layout.addLayout(state_layout)

    def _setup_special_days_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Sonder-Arbeitstage (z.B. 24.12.):</b>"))
        self.special_days_table = QTableWidget(0, 3)
        self.special_days_table.setHorizontalHeaderLabels(["Tag", "Monat", "Soll-Zeit"])
        self.special_days_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.special_days_table.setFixedHeight(120)
        layout.addWidget(self.special_days_table)

        special_btn_layout = QHBoxLayout()
        btn_add_special = QPushButton("Hinzufügen")
        btn_add_special.clicked.connect(self.add_special_day_row)
        btn_remove_special = QPushButton("Löschen")
        btn_remove_special.clicked.connect(self.remove_special_day_row)
        special_btn_layout.addWidget(btn_add_special)
        special_btn_layout.addWidget(btn_remove_special)
        layout.addLayout(special_btn_layout)

        special_days = current_settings.get("special_days", [])
        for sd in special_days:
            self.add_special_day_row(sd)

    def _setup_db_path_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Speicherort der Datenbank:</b>"))
        db_path_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setText(current_settings.get("db_path", DB_FILE))
        self.db_path_edit.setReadOnly(True)
        btn_browse_db = QPushButton("Durchsuchen…")
        btn_browse_db.clicked.connect(self.browse_db_path)
        db_path_layout.addWidget(self.db_path_edit)
        db_path_layout.addWidget(btn_browse_db)
        layout.addLayout(db_path_layout)

    def _on_login_time_state_changed(self):
        """
        Aktiviert oder deaktiviert die Startzeit-Eingabe basierend auf der Login-Zeit-Option.
        """
        self.time_start.setEnabled(not self.login_time_cb.isChecked())

    def add_special_day_row(self, data=None):
        """
        Fügt eine Zeile für einen Sonderarbeitstag hinzu.
        """
        if not isinstance(data, dict):
            data = None  # Handle QPushButton click
        row = self.special_days_table.rowCount()
        self.special_days_table.insertRow(row)

        day_spin = QSpinBox()
        day_spin.setRange(1, 31)
        day_spin.setValue(data["day"] if data else 1)
        self.special_days_table.setCellWidget(row, 0, day_spin)

        month_spin = QSpinBox()
        month_spin.setRange(1, 12)
        month_spin.setValue(data["month"] if data else 1)
        self.special_days_table.setCellWidget(row, 1, month_spin)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(QTime.fromString(data["target"] if data else "04:00", "HH:mm"))
        self.special_days_table.setCellWidget(row, 2, time_edit)

    def remove_special_day_row(self):
        """
        Entfernt die aktuell ausgewählte Zeile der Sonderarbeitstage.
        """
        curr = self.special_days_table.currentRow()
        if curr >= 0:
            self.special_days_table.removeRow(curr)

    def browse_db_path(self):
        """
        Öffnet einen Dateidialog zur Auswahl des Speicherorts der Datenbank.
        """
        path, _ = QFileDialog.getSaveFileName(
            self, "Datenbank speichern unter",
            self.db_path_edit.text(),
            "SQLite Datenbank (*.db);;Alle Dateien (*)"
        )
        if path:
            self.db_path_edit.setText(path)

    def get_settings(self):
        """
        Gibt die im Dialog eingestellten Werte als Dictionary zurück.
        """
        workdays = [i for i, cb in enumerate(self.workday_checkboxes) if cb.isChecked()]
        special_days = []
        for r in range(self.special_days_table.rowCount()):
            day = self.special_days_table.cellWidget(r, 0).value()
            month = self.special_days_table.cellWidget(r, 1).value()
            target = self.special_days_table.cellWidget(r, 2).time().toString("HH:mm")
            special_days.append({"day": day, "month": month, "target": target})

        return {
            "default_start": self.time_start.time().toString("HH:mm"),
            "target_work_time": self.time_target.time().toString("HH:mm"),
            "state": self.state_combo.currentData(),
            "dark_mode": self.dark_mode_cb.isChecked(),
            "max_work_hours": self.max_hours_spin.value(),
            "auto_break": self.auto_break_cb.isChecked(),
            "use_login_time": self.login_time_cb.isChecked(),
            "workdays": workdays,
            "special_days": special_days,
            "db_path": self.db_path_edit.text()
        }


class EditDialog(QDialog):
    """
    Dialog zum Bearbeiten oder Hinzufügen eines Arbeitseintrags.
    """
    def __init__(self, entry: WorkEntry, all_entries: list, target_minutes: int,
                 max_minutes: int = 600, auto_break: bool = True, parent=None):
        """
        Initialisiert den Bearbeitungsdialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Eintrag bearbeiten")
        self.resize(450, 300)
        self.entry = entry
        self.all_entries = all_entries  # All entries to filter by date
        self.target_minutes = target_minutes
        self.max_minutes = max_minutes
        self.auto_break = auto_break
        layout = QVBoxLayout(self)

        self._setup_date_and_times_ui(layout)
        self._setup_minutes_and_reason_ui(layout)
        self._setup_custom_target_ui(layout)

        btn_save = QPushButton("Speichern")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

        if bool(self.entry.start and self.entry.end):
            self.recalc_minutes()

    def _setup_date_and_times_ui(self, layout):
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if self.entry.date:
            self.date_edit.setDate(QDate.fromString(self.entry.date, "yyyy-MM-dd"))
        layout.addWidget(QLabel("Datum:"))
        layout.addWidget(self.date_edit)

        self.has_times_cb = QCheckBox("Start- und Endzeit verwenden")
        has_times = bool(self.entry.start and self.entry.end)
        self.has_times_cb.setChecked(has_times)
        self.has_times_cb.stateChanged.connect(self.toggle_times)
        layout.addWidget(self.has_times_cb)

        time_layout = QHBoxLayout()
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.time_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("HH:mm")
        time_layout.addWidget(QLabel("Ende:"))
        time_layout.addWidget(self.time_end)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 300)
        self.pause_spin.setSuffix(" Min")
        self.pause_spin.setValue(self.entry.pause)
        self.pause_spin.setEnabled(not self.auto_break)
        time_layout.addWidget(QLabel("Pause:"))
        time_layout.addWidget(self.pause_spin)
        layout.addLayout(time_layout)

        if has_times:
            self.time_start.setTime(QTime.fromString(self.entry.start, "HH:mm"))
            self.time_end.setTime(QTime.fromString(self.entry.end, "HH:mm"))
        else:
            self.time_start.setTime(QTime(7, 0))
            self.time_end.setTime(QTime(15, 30))
            self.time_start.setEnabled(False)
            self.time_end.setEnabled(False)
            self.pause_spin.setEnabled(False)

        self.time_start.timeChanged.connect(self.recalc_minutes)
        self.time_end.timeChanged.connect(self.recalc_minutes)
        self.pause_spin.valueChanged.connect(self.recalc_minutes)
        self.date_edit.dateChanged.connect(self.recalc_minutes)

    def _setup_minutes_and_reason_ui(self, layout):
        self.min_spinbox = QSpinBox()
        self.min_spinbox.setRange(-2000, 2000)
        self.min_spinbox.setValue(self.entry.minutes)
        layout.addWidget(QLabel("Minuten (Überstunden):"))
        layout.addWidget(self.min_spinbox)

        self.reason_edit = QLineEdit()
        self.reason_edit.setText(self.entry.reason)
        layout.addWidget(QLabel("Anlass:"))
        layout.addWidget(self.reason_edit)

    def _setup_custom_target_ui(self, layout):
        self.custom_target_cb = QCheckBox("Individuelles Tagessoll für diesen Tag")
        self.custom_target_cb.setChecked(self.entry.target_minutes != -1)
        self.custom_target_time = QTimeEdit()
        self.custom_target_time.setDisplayFormat("HH:mm")
        if self.entry.target_minutes != -1:
            self.custom_target_time.setTime(QTime(self.entry.target_minutes // 60,
                                                  self.entry.target_minutes % 60))
        else:
            def_target = self.parent().settings.get("target_work_time", "08:00")
            self.custom_target_time.setTime(QTime.fromString(def_target, "HH:mm"))

        self.custom_target_time.setEnabled(self.custom_target_cb.isChecked())
        self.custom_target_cb.stateChanged.connect(self._on_custom_target_changed)
        self.custom_target_cb.stateChanged.connect(self.recalc_minutes)
        self.custom_target_time.timeChanged.connect(self.recalc_minutes)

        target_layout = QHBoxLayout()
        target_layout.addWidget(self.custom_target_cb)
        target_layout.addWidget(self.custom_target_time)
        layout.addLayout(target_layout)


    def _on_custom_target_changed(self):
        """
        Aktiviert oder deaktiviert das Zeit-Eingabefeld für das individuelle Tagessoll.
        """
        self.custom_target_time.setEnabled(self.custom_target_cb.isChecked())

    def toggle_times(self, _state):
        """
        Aktiviert oder deaktiviert die Zeit-Eingabefelder basierend auf der Checkbox.
        """
        is_checked = self.has_times_cb.isChecked()
        self.time_start.setEnabled(is_checked)
        self.time_end.setEnabled(is_checked)
        self.pause_spin.setEnabled(is_checked and not self.auto_break)
        if is_checked:
            self.recalc_minutes()

    def recalc_minutes(self):
        """
        Berechnet die Überstunden automatisch basierend auf Start-, Endzeit und Pause.
        """
        if not self.has_times_cb.isChecked():
            return

        curr_date_str = self.date_edit.date().toString("yyyy-MM-dd")
        target_mins = self.parent().get_target_minutes_for_date(curr_date_str)

        current_temp = WorkEntry(
            id=self.entry.id,
            date=curr_date_str,
            start=self.time_start.time().toString("HH:mm"),
            end=self.time_end.time().toString("HH:mm"),
            pause=self.pause_spin.value() if not self.auto_break else 0,
            minutes=0,
            reason=""
        )

        other_timed = [e for e in self.all_entries
                       if e.date == curr_date_str and e.id != self.entry.id and e.start and e.end]
        results, _ = calculate_timed_entries(other_timed + [current_temp],
                                             target_mins, self.max_minutes, self.auto_break)
        entry_pause, entry_overtime = results[self.entry.id]

        if self.auto_break:
            self.pause_spin.blockSignals(True)
            self.pause_spin.setValue(entry_pause)
            self.pause_spin.blockSignals(False)

        self.min_spinbox.setValue(entry_overtime)

    def apply_to_entry(self):
        """
        Übernimmt die Werte aus dem Dialog in das übergebene WorkEntry-Objekt.
        """
        self.entry.date = self.date_edit.date().toString("yyyy-MM-dd")
        self.entry.minutes = self.min_spinbox.value()
        self.entry.reason = self.reason_edit.text().strip()

        if self.custom_target_cb.isChecked():
            t = self.custom_target_time.time()
            self.entry.target_minutes = t.hour() * 60 + t.minute()
        else:
            self.entry.target_minutes = -1

        if self.has_times_cb.isChecked():
            self.entry.start = self.time_start.time().toString("HH:mm")
            self.entry.end = self.time_end.time().toString("HH:mm")
            self.entry.pause = self.pause_spin.value()
        else:
            self.entry.start = ""
            self.entry.end = ""
            self.entry.pause = 0
