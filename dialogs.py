
"""
Dialog-Fenster für Einstellungen und zum Bearbeiten von Einträgen.
"""
from PyQt6.QtCore import QDate, QLocale, QTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog,
    QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTabWidget, QTimeEdit, QVBoxLayout, QWidget
)
from config import DB_FILE, get_country_list, get_subdivisions
from i18n import available_languages, get_locale, tr
from models import WorkEntry
from logic import calculate_timed_entries, is_midnight_shift

# pylint: disable=too-many-instance-attributes, too-many-arguments
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
        self.setWindowTitle(tr("Einstellungen"))
        self.resize(500, 480)
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Arbeitszeit & Pausen
        tab_work = QWidget()
        layout_work = QVBoxLayout(tab_work)
        self._setup_time_settings_ui(layout_work, current_settings)
        self._setup_workdays_ui(layout_work, current_settings)
        layout_work.addSpacing(10)
        layout_work.addWidget(QLabel(f"<b>{tr('Pausen-Regelung:')}</b>"))
        self.auto_break_cb = QCheckBox(tr("Automatische Pausen-Berechnung"))
        self.auto_break_cb.setChecked(current_settings.get("auto_break", True))
        layout_work.addWidget(self.auto_break_cb)
        self._setup_break_rules_ui(layout_work, current_settings)
        layout_work.addStretch()
        self.tabs.addTab(tab_work, tr("Arbeitszeit && Pause"))

        # Tab 2: Region & Feiertage
        tab_region = QWidget()
        layout_region = QVBoxLayout(tab_region)
        self._setup_regional_ui(layout_region, current_settings)
        self._setup_special_days_ui(layout_region, current_settings)
        layout_region.addStretch()
        self.tabs.addTab(tab_region, tr("Region && Feiertage"))

        # Tab 3: System & Darstellung
        tab_system = QWidget()
        layout_system = QVBoxLayout(tab_system)
        layout_system.addWidget(QLabel(f"<b>{tr('Darstellung:')}</b>"))
        self.dark_mode_cb = QCheckBox(tr("Dark Mode aktivieren"))
        self.dark_mode_cb.setChecked(current_settings.get("dark_mode", False))
        layout_system.addWidget(self.dark_mode_cb)
        layout_system.addSpacing(10)
        self._setup_db_path_ui(layout_system, current_settings)
        layout_system.addStretch()
        self.tabs.addTab(tab_system, tr("System && Design"))

        self.btn_save = QPushButton(tr("Speichern"))
        self.btn_save.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_save)

    def _setup_workdays_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel(f"<b>{tr('Arbeitstage (Soll-Tage):')}</b>"))
        self.workday_checkboxes = []
        workdays_layout = QHBoxLayout()
        days = [get_locale().dayName(i + 1, QLocale.FormatType.ShortFormat)
                for i in range(7)]
        selected_workdays = current_settings.get("workdays", [0, 1, 2, 3, 4])
        for i, day_name in enumerate(days):
            cb = QCheckBox(day_name)
            cb.setChecked(i in selected_workdays)
            workdays_layout.addWidget(cb)
            self.workday_checkboxes.append(cb)
        layout.addLayout(workdays_layout)

    def _setup_time_settings_ui(self, layout, current_settings):
        layout.addWidget(QLabel(f"<b>{tr('Tages-Standardwerte:')}</b>"))

        self.login_time_cb = QCheckBox(tr("Login-Zeit als Startzeit verwenden"))
        self.login_time_cb.setToolTip(tr(
            "Liest beim Programmstart die letzte Anmeldezeit des Benutzers aus.\n"
            "Die Standard-Startzeit dient als Fallback, falls die Anmeldezeit\n"
            "nicht ermittelt werden kann."
        ))
        self.login_time_cb.setChecked(current_settings.get("use_login_time", False))
        layout.addWidget(self.login_time_cb)

        time_layout = QHBoxLayout()
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(
            get_locale().timeFormat(QLocale.FormatType.ShortFormat)
        )
        default_start = current_settings.get("default_start", "07:00")
        self.time_start.setTime(QTime.fromString(default_start, "HH:mm"))
        self.time_start.setEnabled(not current_settings.get("use_login_time", False))
        self.login_time_cb.stateChanged.connect(self._on_login_time_state_changed)
        time_layout.addWidget(QLabel(tr("Fallback Startzeit:")))
        time_layout.addWidget(self.time_start)
        layout.addLayout(time_layout)

        target_layout = QHBoxLayout()
        self.time_target = QTimeEdit()
        self.time_target.setDisplayFormat("HH:mm")
        target_work_time = current_settings.get("target_work_time", "08:00")
        self.time_target.setTime(QTime.fromString(target_work_time, "HH:mm"))
        target_layout.addWidget(QLabel(tr("Regelarbeitszeit (Soll):")))
        target_layout.addWidget(self.time_target)
        layout.addLayout(target_layout)

        max_layout = QHBoxLayout()
        self.max_hours_spin = QSpinBox()
        self.max_hours_spin.setRange(6, 24)
        self.max_hours_spin.setSuffix(" h")
        self.max_hours_spin.setValue(current_settings.get("max_work_hours", 10))
        max_layout.addWidget(QLabel(tr("Max. anrechenbare Arbeitszeit:")))
        max_layout.addWidget(self.max_hours_spin)
        layout.addLayout(max_layout)

    def _setup_break_rules_ui(self, layout, current_settings):
        self.break_rules_table = QTableWidget(0, 2)
        self.break_rules_table.setHorizontalHeaderLabels(
            [tr("Ab Arbeitszeit (h:mm)"), tr("Pause (min)")]
        )
        self.break_rules_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.break_rules_table.setFixedHeight(100)
        layout.addWidget(self.break_rules_table)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton(tr("Hinzufügen"))
        btn_add.clicked.connect(self.add_break_rule_row)
        btn_remove = QPushButton(tr("Löschen"))
        btn_remove.clicked.connect(self.remove_break_rule_row)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)

        rules = current_settings.get("break_rules", [
            {"after": 360, "break": 30},
            {"after": 540, "break": 45},
        ])
        for rule in sorted(rules, key=lambda r: r["after"]):
            self.add_break_rule_row(rule)

    def add_break_rule_row(self, data=None):
        """Fügt eine Zeile für eine Pausenregel hinzu."""
        if not isinstance(data, dict):
            data = None
        row = self.break_rules_table.rowCount()
        self.break_rules_table.insertRow(row)

        after_edit = QTimeEdit()
        after_edit.setDisplayFormat("HH:mm")
        after_mins = data["after"] if data else 360
        after_edit.setTime(QTime(after_mins // 60, after_mins % 60))
        self.break_rules_table.setCellWidget(row, 0, after_edit)

        break_spin = QSpinBox()
        break_spin.setRange(0, 120)
        break_spin.setSuffix(" min")
        break_spin.setValue(data["break"] if data else 30)
        self.break_rules_table.setCellWidget(row, 1, break_spin)

    def remove_break_rule_row(self):
        """Entfernt die aktuell ausgewählte Zeile der Pausenregeln."""
        curr = self.break_rules_table.currentRow()
        if curr >= 0:
            self.break_rules_table.removeRow(curr)

    def _setup_regional_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel(f"<b>{tr('Regionales:')}</b>"))

        lang_layout = QHBoxLayout()
        self.lang_combo = QComboBox()
        for code, name in available_languages():
            self.lang_combo.addItem(name, code)
        curr_lang = current_settings.get("language", "")
        idx = self.lang_combo.findData(curr_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        lang_layout.addWidget(QLabel(tr("Sprache:")))
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addWidget(QLabel(f"<i>{tr('(Neustart erforderlich)')}</i>"))
        layout.addLayout(lang_layout)

        country_layout = QHBoxLayout()
        self.country_combo = QComboBox()
        for code, name in get_country_list():
            self.country_combo.addItem(name, code)
        curr_country = current_settings.get("country", "DE")
        idx = self.country_combo.findData(curr_country)
        if idx >= 0:
            self.country_combo.setCurrentIndex(idx)
        country_layout.addWidget(QLabel(tr("Land:")))
        country_layout.addWidget(self.country_combo)
        layout.addLayout(country_layout)

        subdiv_layout = QHBoxLayout()
        self.state_combo = QComboBox()
        subdiv_layout.addWidget(QLabel(tr("Region (für Feiertage):")))
        subdiv_layout.addWidget(self.state_combo)
        layout.addLayout(subdiv_layout)

        self._update_subdiv_combo(curr_country, current_settings.get("state"))
        self.country_combo.currentIndexChanged.connect(self._on_country_changed)

    def _on_country_changed(self):
        self._update_subdiv_combo(self.country_combo.currentData())

    def _update_subdiv_combo(self, country, current_subdiv=None):
        self.state_combo.clear()
        subdivs = get_subdivisions(country)
        if subdivs:
            for code, name in subdivs:
                self.state_combo.addItem(name, code)
            if current_subdiv:
                idx = self.state_combo.findData(current_subdiv)
                if idx >= 0:
                    self.state_combo.setCurrentIndex(idx)
            self.state_combo.setEnabled(True)
        else:
            self.state_combo.setEnabled(False)

    def _setup_special_days_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel(f"<b>{tr('Sonder-Arbeitstage (z.B. 24.12.):')}</b>"))
        self.special_days_table = QTableWidget(0, 3)
        self.special_days_table.setHorizontalHeaderLabels(
            [tr("Tag"), tr("Monat"), tr("Soll-Zeit")]
        )
        self.special_days_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.special_days_table.setFixedHeight(120)
        layout.addWidget(self.special_days_table)

        special_btn_layout = QHBoxLayout()
        btn_add_special = QPushButton(tr("Hinzufügen"))
        btn_add_special.clicked.connect(self.add_special_day_row)
        btn_remove_special = QPushButton(tr("Löschen"))
        btn_remove_special.clicked.connect(self.remove_special_day_row)
        special_btn_layout.addWidget(btn_add_special)
        special_btn_layout.addWidget(btn_remove_special)
        layout.addLayout(special_btn_layout)

        special_days = current_settings.get("special_days", [])
        for sd in special_days:
            self.add_special_day_row(sd)

    def _setup_db_path_ui(self, layout, current_settings):
        layout.addSpacing(10)
        layout.addWidget(QLabel(f"<b>{tr('Speicherort der Datenbank:')}</b>"))
        db_path_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setText(current_settings.get("db_path", DB_FILE))
        self.db_path_edit.setReadOnly(True)
        btn_browse_db = QPushButton(tr("Durchsuchen…"))
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
            self, tr("Datenbank speichern unter"),
            self.db_path_edit.text(),
            tr("SQLite Datenbank (*.db);;Alle Dateien (*)")
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

        break_rules = []
        for r in range(self.break_rules_table.rowCount()):
            t = self.break_rules_table.cellWidget(r, 0).time()
            after = t.hour() * 60 + t.minute()
            pause = self.break_rules_table.cellWidget(r, 1).value()
            break_rules.append({"after": after, "break": pause})

        return {
            "default_start": self.time_start.time().toString("HH:mm"),
            "target_work_time": self.time_target.time().toString("HH:mm"),
            "language": self.lang_combo.currentData(),
            "country": self.country_combo.currentData(),
            "state": self.state_combo.currentData() if self.state_combo.isEnabled() else None,
            "dark_mode": self.dark_mode_cb.isChecked(),
            "max_work_hours": self.max_hours_spin.value(),
            "auto_break": self.auto_break_cb.isChecked(),
            "use_login_time": self.login_time_cb.isChecked(),
            "workdays": workdays,
            "special_days": special_days,
            "break_rules": break_rules,
            "db_path": self.db_path_edit.text()
        }


# pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-positional-arguments
class EditDialog(QDialog):
    """
    Dialog zum Bearbeiten oder Hinzufügen eines Arbeitseintrags.
    """
    def __init__(self, entry: WorkEntry, all_entries: list, target_minutes: int,
                 max_minutes: int = 600, auto_break: bool = True,
                 break_rules=None, parent=None):
        """
        Initialisiert den Bearbeitungsdialog.
        """
        super().__init__(parent)
        self.setWindowTitle(tr("Eintrag bearbeiten"))
        self.resize(450, 300)
        self.entry = entry
        self.all_entries = all_entries  # All entries to filter by date
        self.target_minutes = target_minutes
        self.max_minutes = max_minutes
        self.auto_break = auto_break
        self.break_rules = break_rules
        layout = QVBoxLayout(self)

        self._setup_date_and_times_ui(layout)
        self._setup_minutes_and_reason_ui(layout)
        self._setup_custom_target_ui(layout)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setStyleSheet("color: #ef4444;")
        self.lbl_warning.setWordWrap(True)
        layout.addWidget(self.lbl_warning)

        btn_save = QPushButton(tr("Speichern"))
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

        if bool(self.entry.start and self.entry.end):
            self.recalc_minutes()

    def _setup_date_and_times_ui(self, layout):
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(
            get_locale().dateFormat(QLocale.FormatType.ShortFormat)
        )
        if self.entry.date:
            self.date_edit.setDate(QDate.fromString(self.entry.date, "yyyy-MM-dd"))
        layout.addWidget(QLabel(tr("Datum:")))
        layout.addWidget(self.date_edit)

        self.has_times_cb = QCheckBox(tr("Start- und Endzeit verwenden"))
        has_times = bool(self.entry.start and self.entry.end)
        self.has_times_cb.setChecked(has_times)
        self.has_times_cb.stateChanged.connect(self.toggle_times)
        layout.addWidget(self.has_times_cb)

        time_layout = QHBoxLayout()
        _time_fmt = get_locale().timeFormat(QLocale.FormatType.ShortFormat)
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(_time_fmt)
        time_layout.addWidget(QLabel(tr("Start:")))
        time_layout.addWidget(self.time_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat(_time_fmt)
        time_layout.addWidget(QLabel(tr("Ende:")))
        time_layout.addWidget(self.time_end)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 300)
        self.pause_spin.setSuffix(" Min")
        self.pause_spin.setValue(self.entry.pause)
        self.pause_spin.setEnabled(not self.auto_break)
        time_layout.addWidget(QLabel(tr("Pause:")))
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
        layout.addWidget(QLabel(tr("Minuten (Überstunden):")))
        layout.addWidget(self.min_spinbox)

        self.reason_edit = QLineEdit()
        self.reason_edit.setText(self.entry.reason)
        layout.addWidget(QLabel(tr("Anlass:")))
        layout.addWidget(self.reason_edit)

    def _setup_custom_target_ui(self, layout):
        self.custom_target_cb = QCheckBox(tr("Individuelles Tagessoll für diesen Tag"))
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
            self.lbl_warning.setText("")
            return

        s_str = self.time_start.time().toString("HH:mm")
        e_str = self.time_end.time().toString("HH:mm")
        
        if is_midnight_shift(s_str, e_str):
            self.lbl_warning.setText(tr("⚠️ Mitternachtsschicht: Wird beim Speichern in zwei Tage aufgeteilt."))
        else:
            self.lbl_warning.setText("")

        curr_date_str = self.date_edit.date().toString("yyyy-MM-dd")
        target_mins = self.parent().get_target_minutes_for_date(curr_date_str)

        current_temp = WorkEntry(
            id=self.entry.id,
            date=curr_date_str,
            start=s_str,
            end=e_str,
            pause=self.pause_spin.value() if not self.auto_break else 0,
            minutes=0,
            reason=""
        )

        other_timed = [e for e in self.all_entries
                       if e.date == curr_date_str and e.id != self.entry.id and e.start and e.end]
        results, _ = calculate_timed_entries(other_timed + [current_temp],
                                             target_mins, self.max_minutes, self.auto_break,
                                             self.break_rules)
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
