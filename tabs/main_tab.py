"""
Eigenständiges Widget für den Haupt-Tab (Eingabe & Liste).
"""
import logging
import os
import shutil
import csv
from datetime import datetime
from io import StringIO

from PyQt6.QtCore import QDate, QLocale, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit,
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTimeEdit,
    QVBoxLayout, QWidget
)

from config import DB_FILE
from dialogs import EditDialog, AbsenceEditDialog
from exports import export_csv, export_xlsx, export_pdf, export_monthly_pdf
from i18n import get_locale, tr
from logic import (
    calculate_timed_entries, get_login_time,
    format_time, fmt_date, fmt_time_hhmm,
    get_target_minutes, get_max_minutes, get_target_minutes_for_date,
    COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_INFO,
    is_midnight_shift, split_midnight_shift,
    TYPE_WORK, TYPE_VACATION, TYPE_SICK, TYPE_HOLIDAY, TYPE_FLEXTIME, TYPE_PARENTAL,
    ABSENCE_TYPES, get_absence_minutes, TYPE_LABELS,
)
from models import WorkEntry
from ui_components import set_overtime_color

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class MainTab(QWidget):  # pylint: disable=too-many-public-methods
    """Haupt-Tab für Zeiterfassung, Eintrags-Liste und Export/Import."""

    data_changed = pyqtSignal()
    filter_changed = pyqtSignal(str)

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(self, db, settings, save_settings_cb, open_settings_cb, parent=None):
        """
        Initialisiert das Haupt-Tab-Widget.

        Args:
            db:               DBManager-Instanz für Datenbankzugriffe.
            settings:         Einstellungs-Dictionary (gemeinsame Referenz).
            save_settings_cb: Callable zum Speichern der Einstellungen.
            open_settings_cb: Callable zum Öffnen des Einstellungs-Dialogs.
            parent:           Eltern-Widget.
        """
        super().__init__(parent)
        self.db = db
        self.settings = settings
        self._save_settings = save_settings_cb
        self._open_settings_cb = open_settings_cb
        self.entries = []
        self.current_calculated_overtime = 0
        self.current_calculated_pause = 0
        self._last_added_params = None

        self._build_ui()

    # pylint: disable=too-many-locals, too-many-statements
    def _build_ui(self):
        """Erstellt das Layout des Haupt-Tabs."""
        layout = QVBoxLayout(self)

        self.lbl_saldo = QLabel("0h 0m")
        self.lbl_saldo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        self.lbl_saldo.setFont(font)
        layout.addWidget(QLabel(f"<b>{tr('Gesamt-Saldo:')}</b>",
                                alignment=Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(self.lbl_saldo)

        frame_input = QFrame()
        frame_layout = QVBoxLayout(frame_input)

        input_row1 = QHBoxLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(
            get_locale().dateFormat(QLocale.FormatType.ShortFormat)
        )
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self.update_live_calc)
        input_row1.addWidget(QLabel(tr("Datum:")))
        input_row1.addWidget(self.date_edit)
        self.date_end_edit = QDateEdit()
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDisplayFormat(
            get_locale().dateFormat(QLocale.FormatType.ShortFormat)
        )
        self.date_end_edit.setDate(QDate.currentDate())
        self.date_end_edit.setEnabled(False)
        self.lbl_date_end = QLabel(tr("bis:"))
        self.lbl_date_end.setEnabled(False)
        input_row1.addWidget(self.lbl_date_end)
        input_row1.addWidget(self.date_end_edit)

        start_to_use = self._get_default_start_time()

        _time_fmt = get_locale().timeFormat(QLocale.FormatType.ShortFormat)
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(_time_fmt)
        self.time_start.setTime(start_to_use)
        self.lbl_start = QLabel(tr("Start:"))
        input_row1.addWidget(self.lbl_start)
        input_row1.addWidget(self.time_start)
        self.btn_now_start = QPushButton(tr("Jetzt"))
        self.btn_now_start.setToolTip(tr("Aktuelle Uhrzeit als Startzeit setzen"))
        self.btn_now_start.clicked.connect(lambda: self.time_start.setTime(QTime.currentTime()))
        input_row1.addWidget(self.btn_now_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat(_time_fmt)
        self.lbl_end = QLabel(tr("Ende:"))
        input_row1.addWidget(self.lbl_end)
        input_row1.addWidget(self.time_end)
        self.btn_now_end = QPushButton(tr("Jetzt"))
        self.btn_now_end.setToolTip(tr("Aktuelle Uhrzeit als Endzeit setzen"))
        self.btn_now_end.clicked.connect(self._set_now_as_end)
        input_row1.addWidget(self.btn_now_end)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 300)
        self.pause_spin.setSuffix(" Min")
        self.pause_spin.setEnabled(not self.settings.get("auto_break", True))
        self.lbl_pause = QLabel(tr("Pause:"))
        self.lbl_pause.setEnabled(self.pause_spin.isEnabled())
        input_row1.addWidget(self.lbl_pause)
        input_row1.addWidget(self.pause_spin)

        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText(tr("z.B. Regulär"))
        self.lbl_reason = QLabel(tr("Anlass:"))
        input_row1.addWidget(self.lbl_reason)
        input_row1.addWidget(self.reason_edit)

        btn_add = QPushButton(tr("Eintragen"))
        btn_add.clicked.connect(self.add_entry)
        input_row1.addWidget(btn_add)

        # Eintragstyp-Auswahl und Urlaubskonto-Anzeige
        input_row2 = QHBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItem(tr("Arbeit"), TYPE_WORK)
        self.type_combo.addItem(tr("Urlaub"), TYPE_VACATION)
        self.type_combo.addItem(tr("Krank"), TYPE_SICK)
        self.type_combo.addItem(tr("Gleitzeitabbau"), TYPE_FLEXTIME)
        self.type_combo.addItem(tr("Elternzeit"), TYPE_PARENTAL)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        input_row2.addWidget(QLabel(tr("Typ:")))
        input_row2.addWidget(self.type_combo)
        input_row2.addStretch()
        self.lbl_vacation = QLabel("")
        self.lbl_vacation.setStyleSheet("color: gray; font-size: 11px;")
        input_row2.addWidget(self.lbl_vacation)
        frame_layout.addLayout(input_row2)

        frame_layout.addLayout(input_row1)

        target_row = QHBoxLayout()
        self.custom_target_cb = QCheckBox(tr("Indiv. Tagessoll:"))
        self.custom_target_time = QTimeEdit()
        self.custom_target_time.setDisplayFormat("HH:mm")
        def_target = self.settings.get("target_work_time", "08:00")
        self.custom_target_time.setTime(QTime.fromString(def_target, "HH:mm"))
        self.custom_target_time.setEnabled(False)
        self.custom_target_cb.stateChanged.connect(
            lambda: self.custom_target_time.setEnabled(self.custom_target_cb.isChecked())
        )
        self.custom_target_cb.stateChanged.connect(self.update_live_calc)
        self.custom_target_time.timeChanged.connect(self.update_live_calc)

        target_row.addWidget(self.custom_target_cb)
        target_row.addWidget(self.custom_target_time)
        target_row.addStretch()
        frame_layout.addLayout(target_row)
        self.lbl_live_calc = QLabel(tr("Berechne..."))
        self.lbl_live_calc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.lbl_live_calc)

        layout.addWidget(frame_input)

        self.time_start.timeChanged.connect(self.on_start_time_changed)
        self.time_end.timeChanged.connect(self.update_live_calc)
        self.pause_spin.valueChanged.connect(self.update_live_calc)

        toolbar_layout = QHBoxLayout()
        self.month_filter = QComboBox()
        self.month_filter.addItem(tr("Alle"), "ALL")
        self.month_filter.currentIndexChanged.connect(self._on_list_filter_changed)
        toolbar_layout.addWidget(QLabel(tr("Filter:")))
        toolbar_layout.addWidget(self.month_filter)
        toolbar_layout.addStretch()

        btn_import = QPushButton(tr("CSV Import"))
        btn_import.clicked.connect(self.import_csv)
        toolbar_layout.addWidget(btn_import)

        btn_export = QPushButton(tr("Export"))
        export_menu = QMenu(self)
        export_menu.addAction(tr("CSV  (.csv)"),
                              lambda: export_csv(self, self._get_export_entries()))
        export_menu.addAction(tr("Excel (.xlsx)"),
                              lambda: export_xlsx(self, self._get_export_entries(),
                                                self._get_export_title()))
        export_menu.addAction(tr("PDF  (.pdf)"),
                              lambda: export_pdf(self, self._get_export_entries(),
                                               self._get_export_title()))
        export_menu.addAction(tr("Monats-PDF (.pdf)"),
                              lambda: export_monthly_pdf(self, self._get_export_entries(),
                                                         self.settings,
                                                         self.month_filter.currentData()
                                                         if self.month_filter.currentData() != "ALL" else None))
        btn_export.setMenu(export_menu)
        toolbar_layout.addWidget(btn_export)

        btn_settings = QPushButton(tr("Einstellungen"))
        btn_settings.clicked.connect(self._open_settings_cb)
        toolbar_layout.addWidget(btn_settings)
        layout.addLayout(toolbar_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            tr("Datum"), tr("Zeitraum"), tr("Überstunden"), tr("Anlass"), tr("Aktion")
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(4, 200) # Platz für Edit & Löschen
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.cellDoubleClicked.connect(self.edit_entry)
        layout.addWidget(self.table)

        self.on_start_time_changed(start_to_use)

    # --- Public interface ---

    def refresh(self, entries):
        """Aktualisiert die Einträge und die Tabellen-Anzeige.

        Args:
            entries: Aktuelle Liste aller WorkEntry-Objekte.
        """
        self.entries = entries
        self.update_ui()
        self.update_live_calc()
        self._update_vacation_summary()

    def set_filter(self, month_str):
        """Setzt den Monatsfilter ohne das filter_changed-Signal auszulösen.

        Args:
            month_str: Monatsstring im Format 'yyyy-MM' oder 'ALL'.
        """
        idx = self.month_filter.findData(month_str)
        if idx >= 0:
            self.month_filter.blockSignals(True)
            self.month_filter.setCurrentIndex(idx)
            self.month_filter.blockSignals(False)
            self.update_ui()

    def set_db(self, db):
        """Ersetzt die Datenbankverbindung (z.B. nach DB-Wechsel in Einstellungen).

        Args:
            db: Neue DBManager-Instanz.
        """
        self.db = db

    def get_target_minutes_for_date(self, date_str):
        """Hilfsmethode für den EditDialog: Ermittelt die Soll-Minuten für ein Datum."""
        return get_target_minutes_for_date(date_str, self.entries, self.settings)

    def on_settings_changed(self):
        """Aktualisiert UI-Elemente nach einer Einstellungsänderung."""
        self.pause_spin.setEnabled(not self.settings.get("auto_break", True))
        new_start = self._get_default_start_time()
        self.time_start.blockSignals(True)
        self.time_start.setTime(new_start)
        self.time_start.blockSignals(False)
        self.on_start_time_changed(new_start)

    def _on_type_changed(self, _index):
        """Bei Nicht-Arbeit: Zeiten/Pause/indiv. Soll/Anlass ausgrauen und das
        Datum-bis (Mehrtages-Bereich) aktivieren."""
        selected = self.type_combo.currentData()
        is_work = selected == TYPE_WORK
        # Komplette Arbeitszeit-Gruppe (Felder + Labels + "Jetzt"-Buttons) ausgrauen.
        # Nach setEnabled muss das QSS neu evaluiert werden (unpolish/polish), sonst
        # greift die :disabled-Regel bei bereits angezeigten Widgets nicht.
        work_widgets = (self.time_start, self.time_end, self.lbl_start, self.lbl_end,
                        self.btn_now_start, self.btn_now_end, self.lbl_pause,
                        self.reason_edit, self.lbl_reason, self.custom_target_cb)
        for w in work_widgets:
            w.setEnabled(is_work)
        self.pause_spin.setEnabled(is_work and not self.settings.get("auto_break", True))
        # Pause-Label folgt dem Feld: bei aktiver Auto-Pause ist beides grau
        self.lbl_pause.setEnabled(self.pause_spin.isEnabled())
        self.custom_target_time.setEnabled(is_work and self.custom_target_cb.isChecked())
        self.date_end_edit.setEnabled(not is_work)
        self.lbl_date_end.setEnabled(not is_work)
        for w in (*work_widgets, self.pause_spin, self.custom_target_time,
                  self.date_end_edit, self.lbl_date_end):
            w.style().unpolish(w)
            w.style().polish(w)
        # Beim Wechsel auf Abwesenheit: Bereich auf Einzeltag (Starttag) setzen,
        # damit nicht versehentlich ein riesiger Zeitraum (bis heute) entsteht.
        if not is_work:
            self.date_end_edit.setDate(self.date_edit.date())
        self.update_live_calc()
        self._update_vacation_summary()

    def recalculate_day(self, date_str):
        """Verteilt Pausen und Überstunden für alle Zeiteinträge eines Tages neu.

        Manuelle Einträge (ohne Start-/Endzeit) werden nicht angefasst.

        Args:
            date_str: Datum im Format 'yyyy-MM-dd'.
        """
        day_entries = [e for e in self.entries if e.date == date_str]
        if not day_entries:
            return
        target_mins = get_target_minutes_for_date(date_str, self.entries, self.settings)
        # Absenz-Einträge: Minuten aus Typ + Tagessoll ableiten (keine Zeitrechnung)
        absence_entries = [e for e in day_entries if e.entry_type in ABSENCE_TYPES]
        for e in absence_entries:
            e.minutes = get_absence_minutes(e.entry_type, target_mins)
            e.pause = 0
            self.db.update(e)
        # Flextime-Einträge: Überstunden ausgeben
        flextime_entries = [e for e in day_entries if e.entry_type == TYPE_FLEXTIME]
        for e in flextime_entries:
            e.minutes = get_absence_minutes(e.entry_type, target_mins)
            e.pause = 0
            self.db.update(e)
        timed = [e for e in day_entries if e.start and e.end and e.entry_type == TYPE_WORK]
        if not timed:
            return
        max_mins = get_max_minutes(self.settings)
        is_auto = self.settings.get("auto_break", True)
        break_rules = self.settings.get("break_rules")
        results, _ = calculate_timed_entries(timed, target_mins, max_mins, is_auto, break_rules)
        for e in timed:
            e.pause, e.minutes = results[e.id]
            self.db.update(e)

    def recalculate_all_days(self):
        """Berechnet alle Tage in der Eintrags-Liste neu (z.B. nach Einstellungsänderung)."""
        all_dates = sorted(set(e.date for e in self.entries))
        for date_str in all_dates:
            self.recalculate_day(date_str)

    # --- UI update ---

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    def update_ui(self):
        """Aktualisiert die Eintrags-Tabelle und den Gesamtsaldo entsprechend dem aktiven Filter."""
        self.month_filter.blockSignals(True)
        current_filter = self.month_filter.currentData()
        self.month_filter.clear()
        self.month_filter.addItem(tr("Alle"), "ALL")

        months = sorted(
            list(set(e.date[:7] for e in self.entries if len(e.date) >= 7)), reverse=True
        )
        for m in months:
            self.month_filter.addItem(f"{m[-2:]}/{m[:4]}", m)
        idx = self.month_filter.findData(current_filter)
        if idx >= 0:
            self.month_filter.setCurrentIndex(idx)
        self.month_filter.blockSignals(False)

        self.table.setRowCount(0)
        filter_val = self.month_filter.currentData()
        total_overall = sum(e.minutes for e in self.entries)

        self._display_blocks = []
        filtered = [e for e in self.entries
                    if filter_val == "ALL" or e.date.startswith(filter_val)]
        blocks = self._consolidate_blocks(filtered)

        for row, block in enumerate(blocks):
            self._display_blocks.append(block)
            self.table.insertRow(row)
            first, last = block[0], block[-1]
            etype = getattr(first, 'entry_type', TYPE_WORK)
            is_multi = len(block) > 1

            date_text = (f"{fmt_date(first.date)} – {fmt_date(last.date)}"
                         if is_multi else fmt_date(first.date))
            item_date = QTableWidgetItem(date_text)
            item_date.setData(Qt.ItemDataRole.UserRole, row)
            item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if etype in ABSENCE_TYPES or etype == TYPE_FLEXTIME:
                z_str = TYPE_LABELS.get(etype, etype)
                if is_multi:
                    z_str += tr(" ({n} Tage)").format(n=len(block))
            else:
                z_str = (
                    f"{fmt_time_hhmm(first.start)} - {fmt_time_hhmm(first.end)}"
                    + (f" (-{first.pause}m)" if first.pause > 0 else "")
                    if first.start else "-"
                )
            item_zeit = QTableWidgetItem(z_str)
            item_zeit.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            block_minutes = sum(e.minutes for e in block)
            item_min = QTableWidgetItem(format_time(block_minutes, show_plus=True))
            item_min.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if block_minutes > 0:
                item_min.setForeground(QColor(COLOR_POSITIVE))
            elif block_minutes < 0:
                item_min.setForeground(QColor(COLOR_NEGATIVE))

            btn_style = "padding: 2px 8px; min-height: 24px;"
            btn_edit = QPushButton(tr("Bearbeiten"))
            btn_edit.setStyleSheet(btn_style)
            btn_edit.clicked.connect(lambda _, blk=block: self._edit_block(blk))

            btn_del = QPushButton(tr("Löschen"))
            btn_del.setStyleSheet(btn_style)
            btn_del.clicked.connect(lambda _, blk=block: self._delete_block(blk))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 3, 4, 3)
            actions_layout.setSpacing(4)
            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_del)

            self.table.setItem(row, 0, item_date)
            self.table.setItem(row, 1, item_zeit)
            self.table.setItem(row, 2, item_min)
            self.table.setItem(row, 3, QTableWidgetItem(first.reason))
            self.table.setCellWidget(row, 4, actions_widget)

        self.lbl_saldo.setText(format_time(total_overall))
        set_overtime_color(self.lbl_saldo, total_overall)

    def _consolidate_blocks(self, entries):
        """Fasst aufeinanderfolgende, gleichartige Abwesenheiten (Urlaub/Krank/
        Gleitzeitabbau/Elternzeit) zu Blöcken zusammen. Nicht-Arbeitstage
        (Wochenende/Feiertag) dazwischen werden überbrückt. Arbeitseinträge
        bleiben immer einzeln. Rückgabe: Liste von Blöcken (je Liste von Einträgen),
        absteigend nach Startdatum sortiert; innerhalb eines Blocks aufsteigend."""
        asc = sorted(entries, key=lambda e: (e.date, e.start or ""))
        blocks = []
        for e in asc:
            etype = getattr(e, "entry_type", TYPE_WORK)
            if etype != TYPE_WORK and blocks:
                prev = blocks[-1]
                if (getattr(prev[-1], "entry_type", TYPE_WORK) == etype
                        and self._only_nonworkdays_between(prev[-1].date, e.date)):
                    prev.append(e)
                    continue
            blocks.append([e])
        blocks.sort(key=lambda b: b[0].date, reverse=True)
        return blocks

    def _only_nonworkdays_between(self, date_a, date_b):
        """True, wenn jeder Kalendertag STRIKT zwischen date_a und date_b ein
        Nicht-Arbeitstag ist (Tagessoll 0 → Wochenende/Feiertag)."""
        qa = QDate.fromString(date_a, "yyyy-MM-dd")
        qb = QDate.fromString(date_b, "yyyy-MM-dd")
        if not qa.isValid() or not qb.isValid():
            return False
        d = qa.addDays(1)
        while d < qb:
            if get_target_minutes_for_date(
                    d.toString("yyyy-MM-dd"), self.entries, self.settings) > 0:
                return False
            d = d.addDays(1)
        return True

    # --- Input helpers ---

    def _get_default_start_time(self):
        """Ermittelt die Startzeit für die Eingabemaske."""
        if self.settings.get("use_login_time", False):
            today = QDate.currentDate().toString("yyyy-MM-dd")
            t = get_login_time()
            if self.settings.get("is_primary_device", False):
                if t and t.isValid():
                    self.db.set_device_login(today, t.toString("HH:mm"))
                    return t
            else:
                shared = self.db.get_device_login(today)
                if shared:
                    return QTime.fromString(shared, "HH:mm")
                if t and t.isValid():
                    return t
            return QTime.fromString(self.settings.get("default_start", "07:00"), "HH:mm")
        today = QDate.currentDate().toString("yyyy-MM-dd")
        if self.settings.get("last_date") == today and self.settings.get("last_start"):
            return QTime.fromString(self.settings["last_start"], "HH:mm")
        return QTime.fromString(self.settings.get("default_start", "07:00"), "HH:mm")

    def _compute_target_end_time(self, new_start):
        """Berechnet die Endzeit so, dass das Tagessoll erreicht wird."""
        curr_date_str = self.date_edit.date().toString("yyyy-MM-dd")
        all_day = [e for e in self.entries if e.date == curr_date_str]
        timed_existing = [e for e in all_day if e.start and e.end]
        manual_sum = sum(e.minutes for e in all_day if not (e.start and e.end))

        if self.custom_target_cb.isChecked():
            t_target = self.custom_target_time.time()
            target_mins = t_target.hour() * 60 + t_target.minute()
        else:
            target_mins = get_target_minutes_for_date(curr_date_str, self.entries, self.settings)

        max_mins = get_max_minutes(self.settings)
        is_auto = self.settings.get("auto_break", True)

        duration_mins = 0
        for duration_mins in range(0, max_mins * 2 + 1):
            temp = WorkEntry(
                id=-1,
                date=curr_date_str,
                start=new_start.toString("HH:mm"),
                end=new_start.addSecs(duration_mins * 60).toString("HH:mm"),
                pause=self.pause_spin.value() if not is_auto else 0,
                minutes=0,
                reason=""
            )
            _, total_net_timed = calculate_timed_entries(
                timed_existing + [temp], target_mins, max_mins, is_auto,
                self.settings.get("break_rules")
            )
            if (total_net_timed + manual_sum) >= target_mins:
                break

        return new_start.addSecs(duration_mins * 60)

    def _set_now_as_end(self):
        """Setzt die Endzeit auf die aktuelle Uhrzeit."""
        self.time_end.setTime(QTime.currentTime())

    def on_start_time_changed(self, new_start_time):
        """Wird aufgerufen, wenn die Startzeit geändert wird."""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        self.settings["last_date"] = today
        self.settings["last_start"] = new_start_time.toString("HH:mm")

        self.time_end.blockSignals(True)
        self.time_end.setTime(self._compute_target_end_time(new_start_time))
        self.time_end.blockSignals(False)
        self.update_live_calc()

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    def update_live_calc(self):
        """Berechnet die Überstunden-Vorschau live und zeigt sie im Label an."""
        curr_date_str = self.date_edit.date().toString("yyyy-MM-dd")

        if self.custom_target_cb.isChecked():
            t_target = self.custom_target_time.time()
            target_mins = t_target.hour() * 60 + t_target.minute()
        else:
            target_mins = get_target_minutes_for_date(curr_date_str, self.entries, self.settings)

        max_mins = get_max_minutes(self.settings)
        is_auto = self.settings.get("auto_break", True)

        current_temp = WorkEntry(
            id=-1,
            date=curr_date_str,
            start=self.time_start.time().toString("HH:mm"),
            end=self.time_end.time().toString("HH:mm"),
            pause=self.pause_spin.value() if not is_auto else 0,
            minutes=0,
            reason=""
        )

        all_day = [e for e in self.entries if e.date == curr_date_str]

        # Intelligenz: Wenn die aktuellen Formular-Zeiten exakt dem entsprechen,
        # was wir gerade gespeichert haben, zählen wir sie in der Vorschau nicht doppelt.
        is_duplicate = (
            hasattr(self, "_last_added_params") and
            self._last_added_params == (
                curr_date_str,
                current_temp.start,
                current_temp.end
            )
        )

        if not is_duplicate:
            _overlap = self.check_overlap(curr_date_str, current_temp.start, current_temp.end)
            if _overlap:
                self.lbl_live_calc.setStyleSheet(f"color: {COLOR_NEGATIVE};")
                self.lbl_live_calc.setText(
                    f"<span style='color: {COLOR_NEGATIVE};'>"
                    f"⚠️ {tr('Überschneidung mit bestehendem Eintrag:')} {_overlap}"
                    f"</span>"
                )
                return

        timed = [e for e in all_day if e.start and e.end]
        if not is_duplicate:
            timed.append(current_temp)

        manual_sum = sum(e.minutes for e in all_day if not (e.start and e.end))

        # Dauerberechnung — Übernacht-Schichten (start > end) rechnet
        # calculate_timed_entries über die 24h-Korrektur korrekt.
        results, total_net = calculate_timed_entries(
            timed, target_mins, max_mins, is_auto, self.settings.get("break_rules")
        )

        # Wenn wir den temp-Eintrag übersprungen haben, nehmen wir die Werte
        # vom letzten echten Eintrag für die Anzeige/Speicherung
        if not is_duplicate:
            entry_pause, entry_overtime = results[-1]
        else:
            # Dummy-Werte oder wir lassen sie wie sie sind
            entry_pause = self.current_calculated_pause
            entry_overtime = self.current_calculated_overtime

        if is_auto and not is_duplicate:
            self.pause_spin.blockSignals(True)
            self.pause_spin.setValue(entry_pause)
            self.pause_spin.blockSignals(False)

        if not is_duplicate:
            self.current_calculated_pause = entry_pause
            self.current_calculated_overtime = entry_overtime

        final_total_overtime = (total_net - target_mins) + manual_sum
        calc_text = tr(
            "Netto (Tag): {net} ➔ <b>{ot} Überstunden (Tag-Saldo)</b>"
        ).format(
            net=format_time(total_net),
            ot=format_time(final_total_overtime, show_plus=True),
        )

        warnings = []
        if total_net >= max_mins:
            warnings.append(tr("⚠️ Max. {h}h erreicht!").format(h=max_mins // 60))

        # Ruhezeit-Prüfung (11 Stunden)
        # Nur zwischen verschiedenen Tagen prüfen (Letzter Eintrag vor heute)
        prev_entry = self.db.get_last_entry_before(curr_date_str)

        if prev_entry and prev_entry.end:
            try:
                dt_prev = datetime.strptime(
                    f"{prev_entry.date} {prev_entry.end}", "%Y-%m-%d %H:%M"
                )
                start_str_curr = self.time_start.time().toString('HH:mm')
                # Wenn Mitternachtsschicht, prüfen wir nur den Start des ersten Teils
                dt_curr = datetime.strptime(
                    f"{curr_date_str} {start_str_curr}", "%Y-%m-%d %H:%M"
                )
                rest_hours = (dt_curr - dt_prev).total_seconds() / 3600
                if 0 < rest_hours < 11:
                    warnings.append(
                        tr("⚠️ Ruhezeit verletzt ({r}h < 11h)").format(r=f"{rest_hours:.1f}")
                    )
            except ValueError as exc:
                logger.debug("Ruhezeit konnte nicht berechnet werden (ungültige Zeitdaten): %s",
                             exc)

        if warnings:
            calc_text += f" <span style='color: {COLOR_NEGATIVE};'>{' | '.join(warnings)}</span>"
            self.lbl_live_calc.setStyleSheet(f"color: {COLOR_NEGATIVE};")
        else:
            self.lbl_live_calc.setStyleSheet("")
        self.lbl_live_calc.setText(calc_text)

    # --- Data modification ---

    def add_entry(self):
        """Fügt Einträge in die DB ein.

        Arbeit: ein Tageseintrag mit Zeiten (inkl. Überschneidungsprüfung).
        Abwesenheit/Gleitzeitabbau: ein Eintrag pro Tag im gewählten
        Datumsbereich; bei Mehrtages-Bereichen werden Nicht-Arbeitstage
        (Soll 0, z. B. Wochenende/Feiertag) übersprungen.
        """
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        start_str = self.time_start.time().toString("HH:mm")
        end_str = self.time_end.time().toString("HH:mm")
        selected_type = self.type_combo.currentData()

        if selected_type == TYPE_WORK:
            overlap = self.check_overlap(date_str, start_str, end_str)
            if overlap:
                QMessageBox.warning(
                    self, tr("Überschneidung"),
                    tr(
                        "Dieser Zeitraum überschneidet sich mit einem existierenden Eintrag:"
                        "\n\n{overlap}\n\nBitte korrigiere die Zeiten."
                    ).format(overlap=overlap)
                )
                return
            self.db.insert(WorkEntry(
                id=None, date=date_str, start=start_str, end=end_str,
                pause=self.current_calculated_pause,
                minutes=self.current_calculated_overtime,
                reason=self.reason_edit.text().strip(),
                target_minutes=(
                    self.custom_target_time.time().hour() * 60
                    + self.custom_target_time.time().minute()
                ) if self.custom_target_cb.isChecked() else -1,
                entry_type=TYPE_WORK,
            ))
            affected_dates = [date_str]
        else:
            # Abwesenheit / Gleitzeitabbau: ein Eintrag pro Tag im Bereich
            start_date = self.date_edit.date()
            end_date = self.date_end_edit.date()
            if end_date < start_date:
                end_date = start_date
            is_range = end_date != start_date
            affected_dates = []
            d = start_date
            while d <= end_date:
                ds = d.toString("yyyy-MM-dd")
                if is_range and get_target_minutes_for_date(
                        ds, self.entries, self.settings) == 0:
                    d = d.addDays(1)
                    continue
                self.db.insert(WorkEntry(
                    id=None, date=ds, start="", end="", pause=0, minutes=0,
                    reason="", target_minutes=-1, entry_type=selected_type,
                ))
                affected_dates.append(ds)
                d = d.addDays(1)

        self.reason_edit.clear()
        self.custom_target_cb.setChecked(False)
        self.date_edit.setDate(QDate.currentDate())

        self.entries = self.db.load_all()
        self._last_added_params = (date_str, start_str, end_str)

        for dd in affected_dates:
            self.recalculate_day(dd)

        self._update_vacation_summary()
        self.data_changed.emit()


    def _update_vacation_summary(self):
        """Aktualisiert die Urlaubskonto-Anzeige (verbrauchte/verfügbare Tage)."""
        current_year = str(QDate.currentDate().year())
        used = sum(1 for e in self.entries
                   if e.entry_type == TYPE_VACATION and e.date.startswith(current_year))
        entitlement = self.settings.get("vacation_entitlement", 30)
        remaining = entitlement - used
        self.lbl_vacation.setText(tr("Urlaub: {u}/{e} Tage übrig").format(
            u=remaining, e=entitlement))

    def edit_entry(self, row, _column):
        """Doppelklick: öffnet den passenden Bearbeiten-Dialog für die Zeile."""
        blocks = getattr(self, "_display_blocks", [])
        if 0 <= row < len(blocks):
            self._edit_block(blocks[row])

    def _edit_block(self, block):
        """Routet zum richtigen Dialog: Einzeleintrag → EditDialog, mehrtägige
        Abwesenheit → AbsenceEditDialog."""
        if len(block) == 1:
            self._open_edit_dialog(block[0])
        else:
            self._open_absence_block_dialog(block)

    def _open_absence_block_dialog(self, block):
        """Bearbeitet eine zusammengefasste Abwesenheit: alte Tageseinträge
        ersetzen durch einen neuen Bereich/Typ (ein Eintrag pro Werktag)."""
        block = sorted(block, key=lambda e: e.date)
        dialog = AbsenceEditDialog(block, self.settings, self)
        if not dialog.exec():
            return
        new_type, start_date, end_date = dialog.get_values()
        if end_date < start_date:
            end_date = start_date
        old_dates = [e.date for e in block]
        for e in block:
            self.db.delete(e.id)
        self.entries = self.db.load_all()
        is_range = end_date != start_date
        new_dates = []
        d = start_date
        while d <= end_date:
            ds = d.toString("yyyy-MM-dd")
            if (not is_range) or get_target_minutes_for_date(
                    ds, self.entries, self.settings) > 0:
                self.db.insert(WorkEntry(
                    id=None, date=ds, start="", end="", pause=0, minutes=0,
                    reason="", target_minutes=-1, entry_type=new_type))
                new_dates.append(ds)
            d = d.addDays(1)
        self.entries = self.db.load_all()
        for ds in sorted(set(old_dates + new_dates)):
            self.recalculate_day(ds)
        self._update_vacation_summary()
        self.data_changed.emit()

    def _open_edit_dialog(self, entry):
        """Öffnet den Bearbeitungs-Dialog für den übergebenen Arbeitseintrag."""
        old_date = entry.date

        dialog = EditDialog(
            entry, self.entries, get_target_minutes(self.settings),
            get_max_minutes(self.settings), self.settings.get("auto_break", True),
            self.settings.get("break_rules"), self
        )
        if dialog.exec():
            new_date = dialog.date_edit.date().toString("yyyy-MM-dd")
            new_start = (
                dialog.time_start.time().toString("HH:mm")
                if dialog.has_times_cb.isChecked() else ""
            )
            new_end = (
                dialog.time_end.time().toString("HH:mm")
                if dialog.has_times_cb.isChecked() else ""
            )

            overlap = self.check_overlap(new_date, new_start, new_end, exclude_id=entry.id)
            if overlap:
                QMessageBox.warning(
                    self, tr("Überschneidung"),
                    tr(
                        "Die Änderungen überschneiden sich mit einem anderen Eintrag:"
                        "\n\n{overlap}\n\nBitte korrigiere die Zeiten."
                    ).format(overlap=overlap)
                )
                return

            # Übernacht-Schichten bleiben EIN Eintrag (siehe add_entry);
            # calculate_timed_entries in recalculate_day rechnet sie korrekt.
            dialog.apply_to_entry()
            self.db.update(entry)
            affected_dates = [old_date, entry.date]

            self.entries = self.db.load_all()
            for d in sorted(list(set(affected_dates))):
                self.recalculate_day(d)
            self.data_changed.emit()

    def _delete_block(self, block):
        """Löscht einen Listen-Block (Einzeleintrag oder zusammengefasste
        mehrtägige Abwesenheit) nach Bestätigung."""
        block = sorted(block, key=lambda e: e.date)
        if len(block) == 1:
            msg = tr("Eintrag vom {d} wirklich löschen?").format(
                d=fmt_date(block[0].date))
        else:
            msg = tr("Abwesenheit vom {a} bis {b} ({n} Tage) wirklich löschen?").format(
                a=fmt_date(block[0].date), b=fmt_date(block[-1].date), n=len(block))
        reply = QMessageBox.question(
            self, tr("Löschen bestätigen"), msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ids = {e.id for e in block}
            dates = sorted({e.date for e in block})
            for eid in ids:
                self.db.delete(eid)
            self.entries = [e for e in self.entries if e.id not in ids]
            for d in dates:
                self.recalculate_day(d)
            self.data_changed.emit()

    def check_overlap(self, date_str, start_str, end_str, exclude_id=None):
        """Prüft, ob sich der Zeitraum mit bestehenden Einträgen überschneidet.

        Berücksichtigt Mitternachtsschichten durch Splitting in zwei Segmente.
        """
        if not start_str or not end_str:
            return None

        # Falls Mitternachtsschicht: In zwei Segmente teilen und beide einzeln prüfen
        if is_midnight_shift(start_str, end_str):
            p1, p2 = split_midnight_shift(date_str, start_str, end_str)
            # Segment 1: Start bis 00:00 am Wahltag
            err1 = self._check_segment_overlap(*p1, exclude_id=exclude_id)
            if err1:
                return err1
            # Segment 2: 00:00 bis Ende am Folgetag
            err2 = self._check_segment_overlap(*p2, exclude_id=exclude_id)
            if err2:
                return err2
            return None

        # Regulärer Fall (keine Mitternachtsschicht)
        return self._check_segment_overlap(date_str, start_str, end_str, exclude_id=exclude_id)

    def _check_segment_overlap(self, date_str, start_str, end_str, exclude_id=None):
        """Hilfsfunktion zur Prüfung eines einzelnen Zeitsegments gegen die DB."""
        for e in self.entries:
            if e.date == date_str and e.start and e.end and e.id != exclude_id:
                # Dauerberechnung mit Mitternachtskorrektur für den Vergleich
                def to_mins(t_str):
                    t = QTime.fromString(t_str, "HH:mm")
                    return t.hour() * 60 + t.minute()

                m_s_new = to_mins(start_str)
                m_e_new = to_mins(end_str)
                if m_e_new <= m_s_new and end_str == "00:00":
                    m_e_new = 24 * 60

                m_s_old = to_mins(e.start)
                m_e_old = to_mins(e.end)
                if m_e_old <= m_s_old: # Bestehender Eintrag ist Mitternachtsschicht
                    # Das sollte nach dem neuen System nicht mehr vorkommen (da gesplittet),
                    # aber für Altdaten oder während der Umstellung:
                    m_e_old = 24 * 60

                # Standard Überlappungs-Check für Intervalle: [s1, e1] und [s2, e2]
                # überlappen, wenn s1 < e2 UND s2 < e1
                if m_s_new < m_e_old and m_s_old < m_e_new:
                    return f"{e.date}: {e.start} - {e.end} ({e.reason or tr('Ohne Anlass')})"
        return None

    # --- Filter sync ---

    def _on_list_filter_changed(self):
        """Wird aufgerufen, wenn der Monatsfilter in der Listenansicht geändert wird."""
        filter_val = self.month_filter.currentData()
        if filter_val and filter_val != "ALL":
            self.filter_changed.emit(filter_val)
        self.update_ui()

    # --- Export / Import ---

    def _get_export_entries(self):
        """Gibt die Einträge gemäß aktivem Filter zurück."""
        filter_val = self.month_filter.currentData()
        return [e for e in self.entries if filter_val == "ALL" or e.date.startswith(filter_val)]

    def _get_export_title(self):
        """Gibt den Titel für Export-Dokumente zurück."""
        filter_val = self.month_filter.currentData()
        return tr("Alle Einträge") if filter_val == "ALL" else tr("Monat {m}").format(m=filter_val)

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches, too-many-nested-blocks
    def import_csv(self):
        """Importiert Einträge aus einer CSV-Datei und fügt sie zur Datenbank hinzu."""
        file_name, _ = QFileDialog.getOpenFileName(
            self, tr("CSV Import"), "", tr("CSV Dateien (*.csv)")
        )
        if not file_name:
            return
        try:
            with open(file_name, newline="", encoding="utf-8", errors="replace") as csvfile:
                content = csvfile.read()
                if not content:
                    return
                delimiter = ";" if ";" in content.split("\n")[0] else ","
                reader = csv.reader(StringIO(content), delimiter=delimiter)

                pending = []
                affected_dates = set()
                for row in reader:
                    if len(row) >= 1:
                        date_str = row[0].strip()
                        if date_str.lower() in ["datum", "date"] or not date_str:
                            continue
                        try:
                            minutes = (
                                int(row[1].strip()) if len(row) > 1 and row[1].strip() else 0
                            )
                        except ValueError:
                            minutes = 0
                        reason = row[2].strip() if len(row) > 2 else ""
                        start_str = row[3].strip() if len(row) > 3 else ""
                        end_str = row[4].strip() if len(row) > 4 else ""
                        try:
                            pause = int(row[5].strip()) if len(row) > 5 else 0
                        except ValueError:
                            pause = 0

                        parsed_date = ""
                        for fmt in ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"):
                            try:
                                parsed_date = datetime.strptime(
                                    date_str, fmt
                                ).strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                pass
                        if not parsed_date:
                            logger.warning(
                                "Datum '%s' konnte in keinem Format geparst werden, "
                                "wird unverändert übernommen", date_str
                            )
                            parsed_date = date_str

                        pending.append(WorkEntry(
                            id=None, date=parsed_date, start=start_str,
                            end=end_str, pause=pause, minutes=minutes, reason=reason
                        ))
                        affected_dates.add(parsed_date)

            if not pending:
                QMessageBox.information(self, tr("Import"),
                                        tr("Keine importierbaren Einträge gefunden."))
                return

            preview_lines = [f"  {e.date}  {e.start}-{e.end}  {e.reason}" for e in pending[:5]]
            if len(pending) > 5:
                preview_lines.append(
                    f"  {tr('… und {n} weitere').format(n=len(pending) - 5)}"
                )

            reply = QMessageBox.question(
                self, tr("Import bestätigen"),
                tr(
                    "{n} Einträge gefunden:\n\n{preview}"
                    "\n\nJetzt importieren?\n"
                    "(Überstunden werden automatisch für jeden Tag berechnet/konsolidiert)"
                ).format(n=len(pending), preview=chr(10).join(preview_lines)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            current_db = self.settings.get("db_path", DB_FILE)
            if os.path.exists(current_db):
                shutil.copy2(current_db, current_db + ".backup")

            self.db.insert_many(pending)

            self.entries = self.db.load_all()
            for d in sorted(list(affected_dates)):
                self.recalculate_day(d)

            self.data_changed.emit()
            QMessageBox.information(
                self, tr("Erfolg"),
                tr(
                    "{n} Einträge importiert!\n"
                    "Tagessalden wurden automatisch berechnet.\n"
                    "Backup der Datenbank angelegt."
                ).format(n=len(pending))
            )

        except Exception as ex:  # pylint: disable=broad-except
            QMessageBox.critical(self, tr("Fehler"),
                                 tr("Fehler beim Import:\n{ex}").format(ex=str(ex)))
