
"""
Dialog-Fenster für Einstellungen und zum Bearbeiten von Einträgen.
"""
import os
import platform

from PyQt6.QtCore import QDate, QLocale, QTime, Qt, PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDateEdit, QDialog, QGridLayout,
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTabWidget, QTimeEdit, QVBoxLayout, QWidget
)
from ui_components import COLOR_BEREITSCHAFT
from config import APP_VERSION, DB_FILE, ICON_PATH, get_country_list, get_subdivisions
from i18n import available_languages, get_locale, tr
from models import WorkEntry
from logic import calculate_timed_entries, is_midnight_shift, \
    TYPE_WORK, TYPE_VACATION, TYPE_SICK, TYPE_HOLIDAY, TYPE_FLEXTIME, TYPE_PARENTAL, \
    ABSENCE_TYPES

class AboutDialog(QDialog):
    """Kleines Info-Fenster mit Programmname, Version und rechtlichen Hinweisen."""

    def __init__(self, parent=None):
        """Baut das 'Über'-Fenster auf."""
        super().__init__(parent)
        self.setWindowTitle(tr("Über Überzeit Rechner"))
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        pixmap = QPixmap(ICON_PATH)
        if not pixmap.isNull():
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setPixmap(pixmap.scaledToWidth(
                96, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(icon_label)

        title = QLabel("Überzeit Rechner")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel(tr("Version {v}").format(v=APP_VERSION))
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(tr("Überstunden- und Arbeitszeit-Rechner"))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: gray;")
        layout.addWidget(desc)

        layout.addSpacing(6)

        tech = QLabel(
            f"Python {platform.python_version()} · "
            f"PyQt6 {PYQT_VERSION_STR} · Qt {QT_VERSION_STR}"
        )
        tech.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tech.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(tech)

        legal = QLabel(tr("© 2026 Micha Weiß · MIT-Lizenz"))
        legal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legal.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(legal)

        layout.addSpacing(6)

        btn_close = QPushButton(tr("Schließen"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


# pylint: disable=too-many-instance-attributes, too-many-arguments
# pylint: disable=attribute-defined-outside-init
class SettingsDialog(QDialog):
    """
    Dialog zum Verwalten der Benutzereinstellungen wie Standardarbeitszeiten,
    Bundesland und Sonderarbeitstage.
    """
    def __init__(self, current_settings, parent=None, backup_cb=None, restore_cb=None):
        """
        Initialisiert den Einstellungsdialog mit den aktuellen Werten.
        """
        super().__init__(parent)
        self._backup_cb = backup_cb
        self._restore_cb = restore_cb
        self._db_path = current_settings.get("db_path", DB_FILE)
        self.setWindowTitle(tr("Einstellungen"))
        self.resize(650, 520)
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Arbeitszeit & Pausen
        tab_work = QWidget()
        layout_work = QVBoxLayout(tab_work)
        self._setup_time_settings_ui(layout_work, current_settings)
        layout_work.addSpacing(10)
        layout_work.addWidget(QLabel(f"<b>{tr('Pausen-Regelung:')}</b>"))
        self.auto_break_cb = QCheckBox(tr("Automatische Pausen-Berechnung"))
        self.auto_break_cb.setChecked(current_settings.get("auto_break", True))
        layout_work.addWidget(self.auto_break_cb)
        self._setup_break_rules_ui(layout_work, current_settings)
        layout_work.addStretch()
        self.tabs.addTab(tab_work, tr("Arbeitszeit && Pause"))

        # Tab: Arbeitstage & Soll pro Wochentag
        tab_days = QWidget()
        layout_days = QVBoxLayout(tab_days)
        self._setup_workdays_ui(layout_days, current_settings)
        ent_layout = QHBoxLayout()
        ent_layout.addWidget(QLabel(tr("Urlaubsanspruch:")))
        self.vacation_spin = QSpinBox()
        self.vacation_spin.setRange(0, 365)
        self.vacation_spin.setValue(current_settings.get("vacation_entitlement", 30))
        ent_layout.addWidget(self.vacation_spin)
        ent_layout.addWidget(QLabel(tr("Tage / Jahr")))
        ent_layout.addStretch()
        layout_days.addLayout(ent_layout)
        layout_days.addSpacing(10)
        layout_days.addStretch()
        self.tabs.addTab(tab_days, tr("Arbeitstage"))

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
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel(tr("Design:")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr("Automatisch (System)"), "auto")
        self.theme_combo.addItem(tr("Hell"), "light")
        self.theme_combo.addItem(tr("Dunkel"), "dark")
        _theme_idx = self.theme_combo.findData(current_settings.get("theme", "auto"))
        self.theme_combo.setCurrentIndex(_theme_idx if _theme_idx >= 0 else 0)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        layout_system.addLayout(theme_layout)

        self._setup_bereitschaft_color_ui(layout_system, current_settings)
        layout_system.addSpacing(10)
        self._setup_type_colors_ui(layout_system, current_settings)
        layout_system.addSpacing(10)
        self._setup_db_path_ui(layout_system, current_settings)
        layout_system.addSpacing(10)
        btn_wizard = QPushButton(tr("Einrichtungsassistenten erneut aufrufen"))
        btn_wizard.clicked.connect(self._open_welcome_wizard)
        layout_system.addWidget(btn_wizard)
        btn_about = QPushButton(tr("Über das Programm"))
        btn_about.clicked.connect(self._open_about)
        layout_system.addWidget(btn_about)
        backup_layout = QHBoxLayout()
        btn_backup = QPushButton(tr("Backup jetzt erstellen"))
        btn_backup.clicked.connect(self._do_backup)
        btn_restore = QPushButton(tr("Aus Backup wiederherstellen"))
        btn_restore.clicked.connect(self._do_restore)
        backup_layout.addWidget(btn_backup)
        backup_layout.addWidget(btn_restore)
        layout_system.addLayout(backup_layout)
        layout_system.addStretch()
        self.tabs.addTab(tab_system, tr("System && Design"))

        self.btn_save = QPushButton(tr("Speichern"))
        self.btn_save.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_save)

    def _setup_workdays_ui(self, layout, current_settings):
        layout.addWidget(QLabel(f"<b>{tr('Arbeitstage & Soll pro Wochentag:')}</b>"))
        layout.addWidget(QLabel(tr("Häkchen = Arbeitstag; die Zeit ist das jeweilige Tagessoll.")))
        self.workday_checkboxes = []
        self.weekday_time_edits = []
        days = [get_locale().dayName(i + 1, QLocale.FormatType.LongFormat)
                for i in range(7)]
        targets = current_settings.get("weekday_targets")
        if not (isinstance(targets, list) and len(targets) == 7):
            tw = current_settings.get("target_work_time", "08:00")
            wd = current_settings.get("workdays", [0, 1, 2, 3, 4])
            targets = [tw if i in wd else "" for i in range(7)]
        default_target = current_settings.get("target_work_time", "08:00")
        grid = QGridLayout()
        for i, day_name in enumerate(days):
            cb = QCheckBox(day_name)
            cb.setChecked(bool(targets[i]))
            time_edit = QTimeEdit()
            time_edit.setDisplayFormat("HH:mm")
            time_edit.setTime(QTime.fromString(targets[i] or default_target, "HH:mm"))
            time_edit.setEnabled(bool(targets[i]))
            cb.stateChanged.connect(
                lambda _s, te=time_edit, c=cb: te.setEnabled(c.isChecked()))
            grid.addWidget(cb, i, 0)
            grid.addWidget(time_edit, i, 1)
            self.workday_checkboxes.append(cb)
            self.weekday_time_edits.append(time_edit)
        layout.addLayout(grid)

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

        self.primary_device_cb = QCheckBox(
            tr("Primäres Gerät (Login-Zeit für andere Geräte bereitstellen)")
        )
        self.primary_device_cb.setToolTip(tr(
            "Speichert die erste Login-Zeit des Tages in der Datenbank.\n"
            "Andere Geräte schlagen diese Zeit als Startzeit vor, sofern die\n"
            "Datenbank in einem geteilten Ordner (z.B. Nextcloud, Dropbox) liegt.\n"
            "Wirkt nur in Verbindung mit \"Login-Zeit als Startzeit verwenden\"."
        ))
        self.primary_device_cb.setChecked(current_settings.get("is_primary_device", False))
        self.primary_device_cb.setEnabled(self.login_time_cb.isChecked())
        layout.addWidget(self.primary_device_cb)

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
        valid_rules = [r for r in rules if isinstance(r, dict)]
        for rule in sorted(valid_rules, key=lambda r: r.get("after", 0)):
            self.add_break_rule_row(rule)

    def add_break_rule_row(self, data=None):
        """Fügt eine Zeile für eine Pausenregel hinzu."""
        if not isinstance(data, dict):
            data = None
        row = self.break_rules_table.rowCount()
        self.break_rules_table.insertRow(row)

        after_edit = QTimeEdit()
        after_edit.setDisplayFormat("HH:mm")
        after_mins = data.get("after", 360) if data else 360
        after_edit.setTime(QTime(after_mins // 60, after_mins % 60))
        self.break_rules_table.setCellWidget(row, 0, after_edit)

        break_spin = QSpinBox()
        break_spin.setRange(0, 120)
        break_spin.setSuffix(" min")
        break_spin.setValue(data.get("break", 30) if data else 30)
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

    def _setup_bereitschaft_color_ui(self, layout, current_settings):
        """Baut die Farbauswahl für die Bereitschaftslinie im Kalender."""
        color_hex = current_settings.get("bereitschaft_color") or COLOR_BEREITSCHAFT
        if not QColor(color_hex).isValid():
            color_hex = COLOR_BEREITSCHAFT
        self.bereitschaft_color = color_hex

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(tr("Farbe der Bereitschaftslinie:")))
        self.bereitschaft_color_btn = QPushButton()
        self.bereitschaft_color_btn.setFixedWidth(80)
        self.bereitschaft_color_btn.clicked.connect(self._pick_bereitschaft_color)
        self._apply_bereitschaft_color_preview()
        color_row.addWidget(self.bereitschaft_color_btn)
        btn_reset = QPushButton(tr("Zurücksetzen"))
        btn_reset.clicked.connect(self._reset_bereitschaft_color)
        color_row.addWidget(btn_reset)
        color_row.addStretch()
        layout.addLayout(color_row)

    def _apply_bereitschaft_color_preview(self):
        """Aktualisiert die Hintergrundfarbe des Vorschau-Buttons."""
        color = QColor(self.bereitschaft_color)
        text_color = "#000000" if color.lightness() > 140 else "#ffffff"
        self.bereitschaft_color_btn.setStyleSheet(
            f"background-color: {self.bereitschaft_color}; color: {text_color};"
            "padding: 4px 8px;"
        )
        self.bereitschaft_color_btn.setText(self.bereitschaft_color.upper())

    def _pick_bereitschaft_color(self):
        """Öffnet QColorDialog zur Farbauswahl und übernimmt das Ergebnis."""
        chosen = QColorDialog.getColor(
            QColor(self.bereitschaft_color), self, tr("Farbe wählen")
        )
        if chosen.isValid():
            self.bereitschaft_color = chosen.name()
            self._apply_bereitschaft_color_preview()

    def _reset_bereitschaft_color(self):
        """Setzt die Bereitschaftsfarbe auf den Default zurück."""
        self.bereitschaft_color = COLOR_BEREITSCHAFT
        self._apply_bereitschaft_color_preview()


    # --- Typ-Farben ---

    def _setup_type_colors_ui(self, layout, current_settings):
        """Baut Farbwähler für jeden Eintragstyp (außer Arbeit)."""
        layout.addWidget(QLabel(f"<b>{tr('Farben für Eintragstypen:')}</b>"))
        type_colors = current_settings.get("type_colors", {})
        self._type_color_btns = {}
        self._type_colors = {}
        types = [
            (TYPE_VACATION, tr("Urlaub")),
            (TYPE_SICK, tr("Krank")),
            (TYPE_FLEXTIME, tr("Gleitzeitabbau")),
            (TYPE_PARENTAL, tr("Elternzeit")),
        ]
        for t_key, t_label in types:
            color = type_colors.get(t_key, "#888888")
            self._type_colors[t_key] = color
            row = QHBoxLayout()
            row.addWidget(QLabel(f"  {t_label}:"))
            btn = QPushButton()
            btn.setFixedWidth(80)
            t = t_key  # capture
            btn.clicked.connect(lambda _, k=t: self._pick_type_color(k))
            row.addWidget(btn)
            row.addStretch()
            layout.addLayout(row)
            self._type_color_btns[t_key] = btn
        self._apply_type_color_buttons()

    def _apply_type_color_buttons(self):
        for t_key, btn in self._type_color_btns.items():
            color = self._type_colors.get(t_key, "#888888")
            qc = QColor(color)
            txt = "#000000" if qc.lightness() > 140 else "#ffffff"
            btn.setStyleSheet(
                f"background-color: {color}; color: {txt}; padding: 4px 8px;")
            btn.setText(color.upper())

    def _pick_type_color(self, t_key):
        chosen = QColorDialog.getColor(
            QColor(self._type_colors.get(t_key, "#888888")),
            self, tr("Farbe wählen"))
        if chosen.isValid():
            self._type_colors[t_key] = chosen.name()
            self._apply_type_color_buttons()

    def _type_colors_dict(self):
        return dict(self._type_colors)

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
        self.primary_device_cb.setEnabled(self.login_time_cb.isChecked())

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
        day_spin.setValue(data.get("day", 1) if data else 1)
        self.special_days_table.setCellWidget(row, 0, day_spin)

        month_spin = QSpinBox()
        month_spin.setRange(1, 12)
        month_spin.setValue(data.get("month", 1) if data else 1)
        self.special_days_table.setCellWidget(row, 1, month_spin)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(QTime.fromString(data.get("target", "04:00") if data else "04:00", "HH:mm"))
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
        Öffnet einen Dateidialog zur Auswahl der zu ladenden Datenbank.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Datenbank laden"),
            self.db_path_edit.text(),
            tr("SQLite Datenbank (*.db);;Alle Dateien (*)")
        )
        if path:
            self.db_path_edit.setText(path)

    def _open_welcome_wizard(self):
        current = {
            "country": self.country_combo.currentData(),
            "state": self.state_combo.currentData() if self.state_combo.isEnabled() else None,
            "target_work_time": self.time_target.time().toString("HH:mm"),
            "workdays": [i for i, cb in enumerate(self.workday_checkboxes) if cb.isChecked()],
        }
        dlg = WelcomeDialog(current, self)
        if dlg.exec():
            result = dlg.get_settings()
            idx = self.country_combo.findData(result["country"])
            if idx >= 0:
                self.country_combo.setCurrentIndex(idx)
            self._update_subdiv_combo(result["country"], result.get("state"))
            self.time_target.setTime(QTime.fromString(result["target_work_time"], "HH:mm"))
            for i, cb in enumerate(self.workday_checkboxes):
                cb.setChecked(i in result["workdays"])

    def _open_about(self):
        """Öffnet das 'Über'-Fenster mit Versions- und Lizenzinfo."""
        AboutDialog(self).exec()

    def _do_backup(self):
        """Erstellt sofort ein Backup über den Callback und meldet das Ergebnis."""
        if not self._backup_cb:
            return
        path = self._backup_cb()
        if path:
            QMessageBox.information(
                self, tr("Backup"), tr("Backup erstellt:\n{p}").format(p=path))
        else:
            QMessageBox.warning(self, tr("Backup"), tr("Backup fehlgeschlagen."))

    def _do_restore(self):
        """Lässt ein Backup auswählen und stellt es nach Rückfrage wieder her."""
        if not self._restore_cb:
            return
        start_dir = os.path.join(
            os.path.dirname(os.path.abspath(self._db_path)), "backups")
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Backup auswählen"), start_dir, tr("Datenbank (*.db)"))
        if not path:
            return
        reply = QMessageBox.question(
            self, tr("Wiederherstellen"),
            tr("Alle aktuellen Daten werden durch das Backup ersetzt. Fortfahren?"))
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._restore_cb(path):
            QMessageBox.information(
                self, tr("Wiederherstellen"), tr("Daten wiederhergestellt."))
        else:
            QMessageBox.warning(
                self, tr("Wiederherstellen"), tr("Wiederherstellung fehlgeschlagen."))

    def get_settings(self):
        """
        Gibt die im Dialog eingestellten Werte als Dictionary zurück.
        """
        weekday_targets = []
        workdays = []
        for i, cb in enumerate(self.workday_checkboxes):
            if cb.isChecked():
                weekday_targets.append(self.weekday_time_edits[i].time().toString("HH:mm"))
                workdays.append(i)
            else:
                weekday_targets.append("")
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
            "theme": self.theme_combo.currentData(),
            "max_work_hours": self.max_hours_spin.value(),
            "auto_break": self.auto_break_cb.isChecked(),
            "use_login_time": self.login_time_cb.isChecked(),
            "is_primary_device": self.primary_device_cb.isChecked(),
            "workdays": workdays,
            "weekday_targets": weekday_targets,
            "vacation_entitlement": self.vacation_spin.value(),
            "special_days": special_days,
            "break_rules": break_rules,
            "bereitschaft_color": self.bereitschaft_color,
            "type_colors": self._type_colors_dict(),
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

        self.type_combo = QComboBox()
        self.type_combo.addItem(tr("Arbeit"), TYPE_WORK)
        self.type_combo.addItem(tr("Urlaub"), TYPE_VACATION)
        self.type_combo.addItem(tr("Krank"), TYPE_SICK)
        self.type_combo.addItem(tr("Gleitzeitabbau"), TYPE_FLEXTIME)
        self.type_combo.addItem(tr("Elternzeit"), TYPE_PARENTAL)
        _idx = self.type_combo.findData(getattr(self.entry, 'entry_type', TYPE_WORK))
        self.type_combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        self.type_combo.currentIndexChanged.connect(self._on_edit_type_changed)
        layout.addWidget(QLabel(tr("Typ:")))
        layout.addWidget(self.type_combo)

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

    def _on_edit_type_changed(self, _index):
        """Bei Nicht-Arbeit: Zeiten/Pause/indiv. Soll/Anlass ausgrauen."""
        selected = self.type_combo.currentData()
        is_work = selected == TYPE_WORK
        self.reason_edit.setEnabled(is_work)
        self.has_times_cb.setEnabled(is_work)
        # custom_target_* wird erst nach diesem Combo aufgebaut → defensiv prüfen
        if hasattr(self, "custom_target_cb"):
            self.custom_target_cb.setEnabled(is_work)
            self.custom_target_time.setEnabled(is_work and self.custom_target_cb.isChecked())
        if not is_work:
            self.has_times_cb.setChecked(False)
            self.toggle_times(0)

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
            msg = tr("⚠️ Mitternachtsschicht: Wird als ein Eintrag dem Starttag zugerechnet.")
            self.lbl_warning.setText(msg)
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
        self.entry.entry_type = self.type_combo.currentData()

        if self.has_times_cb.isChecked():
            self.entry.start = self.time_start.time().toString("HH:mm")
            self.entry.end = self.time_end.time().toString("HH:mm")
            self.entry.pause = self.pause_spin.value()
        else:
            self.entry.start = ""
            self.entry.end = ""
            self.entry.pause = 0


# pylint: disable=too-few-public-methods
class WelcomeDialog(QDialog):
    """Erster-Start-Dialog für grundlegende Konfiguration."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Willkommen"))
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 24)

        self._setup_header(layout)
        self._setup_location(layout, settings)
        self._setup_schedule(layout, settings)
        layout.addStretch()
        self._setup_buttons(layout)

    def _setup_header(self, layout):
        lbl_title = QLabel(tr("Willkommen beim Überzeit Rechner"))
        font_title = QFont()
        font_title.setPointSize(14)
        font_title.setBold(True)
        lbl_title.setFont(font_title)
        lbl_title.setWordWrap(True)
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(tr(
            "Bitte triff ein paar grundlegende Einstellungen, "
            "damit die App von Anfang an korrekt rechnet."
        ))
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

    def _setup_location(self, layout, settings):
        country_row = QHBoxLayout()
        country_row.addWidget(QLabel(tr("Land:")))
        self.country_combo = QComboBox()
        for code, name in get_country_list():
            self.country_combo.addItem(name, code)
        idx = self.country_combo.findData(settings.get("country", "DE"))
        if idx >= 0:
            self.country_combo.setCurrentIndex(idx)
        country_row.addWidget(self.country_combo)
        layout.addLayout(country_row)

        region_row = QHBoxLayout()
        region_row.addWidget(QLabel(tr("Region (für Feiertage):")))
        self.region_combo = QComboBox()
        region_row.addWidget(self.region_combo)
        layout.addLayout(region_row)
        self.country_combo.currentIndexChanged.connect(self._update_regions)
        self._update_regions()
        idx = self.region_combo.findData(settings.get("state", ""))
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)

    def _setup_schedule(self, layout, settings):
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(tr("Regelarbeitszeit (Soll):")))
        self.time_target = QTimeEdit()
        self.time_target.setDisplayFormat("HH:mm")
        self.time_target.setTime(
            QTime.fromString(settings.get("target_work_time", "08:00"), "HH:mm")
        )
        target_row.addWidget(self.time_target)
        target_row.addStretch()
        layout.addLayout(target_row)

        layout.addWidget(QLabel(f"<b>{tr('Arbeitstage (Soll-Tage):')}</b>"))
        self.workday_checkboxes = []
        workdays_layout = QHBoxLayout()
        days = [get_locale().dayName(i + 1, QLocale.FormatType.ShortFormat) for i in range(7)]
        selected = settings.get("workdays", [0, 1, 2, 3, 4])
        for i, day_name in enumerate(days):
            cb = QCheckBox(day_name)
            cb.setChecked(i in selected)
            workdays_layout.addWidget(cb)
            self.workday_checkboxes.append(cb)
        layout.addLayout(workdays_layout)

        self.login_time_cb = QCheckBox(tr("Login-Zeit als Startzeit verwenden"))
        self.login_time_cb.setToolTip(tr(
            "Liest beim Programmstart die letzte Anmeldezeit des Benutzers aus.\n"
            "Die Standard-Startzeit dient als Fallback, falls die Anmeldezeit\n"
            "nicht ermittelt werden kann."
        ))
        self.login_time_cb.setChecked(settings.get("use_login_time", True))
        layout.addWidget(self.login_time_cb)

    def _setup_buttons(self, layout):
        btn_row = QHBoxLayout()
        btn_skip = QPushButton(tr("Überspringen"))
        btn_skip.clicked.connect(self.reject)
        btn_start = QPushButton(tr("Los geht's →"))
        btn_start.setDefault(True)
        btn_start.clicked.connect(self.accept)
        btn_row.addWidget(btn_skip)
        btn_row.addStretch()
        btn_row.addWidget(btn_start)
        layout.addLayout(btn_row)

    def _update_regions(self):
        """Aktualisiert die Regions-Auswahl basierend auf dem gewählten Land."""
        self.region_combo.clear()
        subdivs = get_subdivisions(self.country_combo.currentData() or "DE")
        for code, name in subdivs:
            self.region_combo.addItem(name, code)
        self.region_combo.setEnabled(bool(subdivs))

    def get_settings(self):
        """Gibt die gewählten Einstellungen als Dict zurück."""
        return {
            "country": self.country_combo.currentData() or "DE",
            "state": self.region_combo.currentData() or "",
            "target_work_time": self.time_target.time().toString("HH:mm"),
            "workdays": [i for i, cb in enumerate(self.workday_checkboxes) if cb.isChecked()],
            "use_login_time": self.login_time_cb.isChecked(),
        }


class AbsenceEditDialog(QDialog):
    """Bearbeiten einer (mehrtägigen) Abwesenheit: Typ und Datum von/bis."""

    def __init__(self, block, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Abwesenheit bearbeiten"))
        self.setMinimumWidth(340)
        block = sorted(block, key=lambda e: e.date)
        cur_type = getattr(block[0], "entry_type", TYPE_VACATION)

        layout = QVBoxLayout(self)
        self.type_combo = QComboBox()
        self.type_combo.addItem(tr("Urlaub"), TYPE_VACATION)
        self.type_combo.addItem(tr("Krank"), TYPE_SICK)
        self.type_combo.addItem(tr("Gleitzeitabbau"), TYPE_FLEXTIME)
        self.type_combo.addItem(tr("Elternzeit"), TYPE_PARENTAL)
        _idx = self.type_combo.findData(cur_type)
        self.type_combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        layout.addWidget(QLabel(tr("Typ:")))
        layout.addWidget(self.type_combo)

        _fmt = get_locale().dateFormat(QLocale.FormatType.ShortFormat)
        self.start_edit = QDateEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat(_fmt)
        self.start_edit.setDate(QDate.fromString(block[0].date, "yyyy-MM-dd"))
        layout.addWidget(QLabel(tr("Von:")))
        layout.addWidget(self.start_edit)

        self.end_edit = QDateEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat(_fmt)
        self.end_edit.setDate(QDate.fromString(block[-1].date, "yyyy-MM-dd"))
        layout.addWidget(QLabel(tr("Bis:")))
        layout.addWidget(self.end_edit)

        btns = QHBoxLayout()
        btn_ok = QPushButton(tr("Speichern"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(tr("Abbrechen"))
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def get_values(self):
        """(entry_type, start_QDate, end_QDate)."""
        return (self.type_combo.currentData(),
                self.start_edit.date(), self.end_edit.date())
