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
from dialogs import EditDialog
from exports import export_csv, export_xlsx, export_pdf
from i18n import get_locale, tr
from logic import (
    calculate_timed_entries, get_login_time,
    format_time, fmt_date, fmt_time_hhmm,
    get_target_minutes, get_max_minutes, get_target_minutes_for_date,
    COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_INFO,
    is_midnight_shift, split_midnight_shift,
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

        start_to_use = self._get_default_start_time()

        _time_fmt = get_locale().timeFormat(QLocale.FormatType.ShortFormat)
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat(_time_fmt)
        self.time_start.setTime(start_to_use)
        input_row1.addWidget(QLabel(tr("Start:")))
        input_row1.addWidget(self.time_start)
        btn_now_start = QPushButton(tr("Jetzt"))
        btn_now_start.setToolTip(tr("Aktuelle Uhrzeit als Startzeit setzen"))
        btn_now_start.clicked.connect(lambda: self.time_start.setTime(QTime.currentTime()))
        input_row1.addWidget(btn_now_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat(_time_fmt)
        input_row1.addWidget(QLabel(tr("Ende:")))
        input_row1.addWidget(self.time_end)
        btn_now_end = QPushButton(tr("Jetzt"))
        btn_now_end.setToolTip(tr("Aktuelle Uhrzeit als Endzeit setzen"))
        btn_now_end.clicked.connect(self._set_now_as_end)
        input_row1.addWidget(btn_now_end)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 300)
        self.pause_spin.setSuffix(" Min")
        self.pause_spin.setEnabled(not self.settings.get("auto_break", True))
        input_row1.addWidget(QLabel(tr("Pause:")))
        input_row1.addWidget(self.pause_spin)

        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText(tr("z.B. Regulär"))
        input_row1.addWidget(QLabel(tr("Anlass:")))
        input_row1.addWidget(self.reason_edit)

        btn_add = QPushButton(tr("Eintragen"))
        btn_add.clicked.connect(self.add_entry)
        input_row1.addWidget(btn_add)

        frame_layout.addLayout(input_row1)

        input_row2 = QHBoxLayout()
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

        input_row2.addWidget(self.custom_target_cb)
        input_row2.addWidget(self.custom_target_time)
        input_row2.addStretch()
        frame_layout.addLayout(input_row2)

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

    def recalculate_day(self, date_str):
        """Verteilt Pausen und Überstunden für alle Zeiteinträge eines Tages neu.

        Manuelle Einträge (ohne Start-/Endzeit) werden nicht angefasst.

        Args:
            date_str: Datum im Format 'yyyy-MM-dd'.
        """
        day_entries = [e for e in self.entries if e.date == date_str]
        if not day_entries:
            return
        timed = [e for e in day_entries if e.start and e.end]
        if not timed:
            return

        target_mins = get_target_minutes_for_date(date_str, self.entries, self.settings)
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

        row = 0
        for i, e in enumerate(self.entries):
            if filter_val != "ALL" and not e.date.startswith(filter_val):
                continue

            self.table.insertRow(row)
            item_date = QTableWidgetItem(fmt_date(e.date))
            item_date.setData(Qt.ItemDataRole.UserRole, i)
            item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            z_str = (
                f"{fmt_time_hhmm(e.start)} - {fmt_time_hhmm(e.end)}"
                + (f" (-{e.pause}m)" if e.pause > 0 else "")
                if e.start else "-"
            )
            item_zeit = QTableWidgetItem(z_str)
            item_zeit.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_min = QTableWidgetItem(format_time(e.minutes, show_plus=True))
            item_min.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if e.minutes > 0:
                item_min.setForeground(QColor(COLOR_POSITIVE))
            elif e.minutes < 0:
                item_min.setForeground(QColor(COLOR_NEGATIVE))

            # Aktion-Spalte mit Buttons für Bearbeiten und Löschen
            btn_style = "padding: 2px 8px; min-height: 24px;"
            btn_edit = QPushButton(tr("Bearbeiten"))
            btn_edit.setStyleSheet(btn_style)
            btn_edit.clicked.connect(lambda _, ent=e: self._open_edit_dialog(ent))

            btn_del = QPushButton(tr("Löschen"))
            btn_del.setStyleSheet(btn_style)
            btn_del.clicked.connect(lambda _, ent=e: self.delete_entry(ent))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 1, 4, 1)
            actions_layout.setSpacing(4)
            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_del)

            self.table.setItem(row, 0, item_date)
            self.table.setItem(row, 1, item_zeit)
            self.table.setItem(row, 2, item_min)
            self.table.setItem(row, 3, QTableWidgetItem(e.reason))
            self.table.setCellWidget(row, 4, actions_widget)
            row += 1

        self.lbl_saldo.setText(format_time(total_overall))
        set_overtime_color(self.lbl_saldo, total_overall)

    # --- Input helpers ---

    def _get_default_start_time(self):
        """Ermittelt die Startzeit für die Eingabemaske."""
        if self.settings.get("use_login_time", False):
            t = get_login_time()
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

        timed = [e for e in all_day if e.start and e.end]
        if not is_duplicate:
            timed.append(current_temp)

        manual_sum = sum(e.minutes for e in all_day if not (e.start and e.end))

        # Dauerberechnung
        if is_midnight_shift(current_temp.start, current_temp.end):
            p1, p2 = split_midnight_shift(curr_date_str, current_temp.start, current_temp.end)

            def get_mins(s, e):
                ts = QTime.fromString(s, "HH:mm")
                te = QTime.fromString(e, "HH:mm")
                diff = ts.secsTo(te) // 60
                if diff < 0:
                    diff += 24 * 60
                return diff

            m1 = get_mins(p1[1], p1[2])
            m2 = get_mins(p2[1], p2[2])
            total_net = m1 + m2 # Vereinfachte Netto-Anzeige für Vorschau

            # Für die Vorschau am aktuellen Tag nehmen wir nur den ersten Teil
            # Aber wir zeigen dem Nutzer, dass es gesplittet wird.
            calc_text = tr(
                "Mitternachtsschicht: {m1}m heute, {m2}m morgen. "
                "Gesamt: {tot}"
            ).format(m1=m1, m2=m2, tot=format_time(total_net))

            # Warnung hinzufügen
            span_style = f"style='color: {COLOR_INFO};'"
            calc_text = f"<span {span_style}>{calc_text} (Wird beim Eintragen gesplittet)</span>"

            self.current_calculated_pause = 0
            self.current_calculated_overtime = 0 # Wird beim recalculate_day nach Split berechnet
        else:
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
        # 1. Letzter Eintrag von GESTERN oder davor
        prev_entry = self.db.get_last_entry_before(curr_date_str)

        # 2. Letzter Eintrag von HEUTE (vor der aktuellen Startzeit)
        curr_day_entries = [e for e in all_day if e.start and e.end and e.id != -1]
        if curr_day_entries:
            # Sortieren nach Endzeit
            last_today = sorted(curr_day_entries, key=lambda x: x.end)[-1]
            # Nur wenn die Endzeit vor der aktuellen Startzeit liegt
            if QTime.fromString(last_today.end, "HH:mm") <= self.time_start.time():
                d_prev_q = QDate.fromString(prev_entry.date, "yyyy-MM-dd")
                d_last_q = QDate.fromString(last_today.date, "yyyy-MM-dd")
                if not prev_entry or d_prev_q < d_last_q or \
                   (prev_entry.date == last_today.date and prev_entry.end < last_today.end):
                    prev_entry = last_today

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
        """Liest die Eingabefelder aus, prüft auf Überlappung und fügt den Eintrag in die DB ein."""
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        start_str = self.time_start.time().toString("HH:mm")
        end_str = self.time_end.time().toString("HH:mm")

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

        # Mitternachts-Splitting
        if is_midnight_shift(start_str, end_str):
            p1, p2 = split_midnight_shift(date_str, start_str, end_str)

            # Eintrag 1 (bis 00:00)
            e1 = WorkEntry(
                id=None, date=p1[0], start=p1[1], end=p1[2],
                pause=0, minutes=0, # Wird durch recalculate_day gesetzt
                reason=self.reason_edit.text().strip(),
                target_minutes=-1 # Bei Split nutzen wir Standard
            )
            # Eintrag 2 (ab 00:00)
            e2 = WorkEntry(
                id=None, date=p2[0], start=p2[1], end=p2[2],
                pause=0, minutes=0,
                reason=self.reason_edit.text().strip(),
                target_minutes=-1
            )
            self.db.insert(e1)
            self.db.insert(e2)

            QMessageBox.information(
                self, tr("Mitternachtsschicht"),
                tr("Der Eintrag wurde auf zwei Tage aufgeteilt:\n"
                   "- {d1}: {s1} - 00:00\n"
                   "- {d2}: 00:00 - {e2}").format(
                       d1=fmt_date(p1[0]), s1=p1[1],
                       d2=fmt_date(p2[0]), e2=p2[2]
                   )
            )
            affected_dates = [p1[0], p2[0]]
        else:
            entry = WorkEntry(
                id=None,
                date=date_str,
                start=start_str,
                end=end_str,
                pause=self.current_calculated_pause,
                minutes=self.current_calculated_overtime,
                reason=self.reason_edit.text().strip(),
                target_minutes=(
                    self.custom_target_time.time().hour() * 60
                    + self.custom_target_time.time().minute()
                ) if self.custom_target_cb.isChecked() else -1
            )
            self.db.insert(entry)
            affected_dates = [date_str]

        self.reason_edit.clear()
        self.custom_target_cb.setChecked(False)
        self.date_edit.setDate(QDate.currentDate())

        self.entries = self.db.load_all()
        self._last_added_params = (date_str, start_str, end_str)

        for d in affected_dates:
            self.recalculate_day(d)

        self.data_changed.emit()

    # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    def edit_entry(self, row, _column):
        """Öffnet den Bearbeitungs-Dialog für den Eintrag in der angeklickten Zeile (Doppelklick)."""
        entry_idx = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        entry = self.entries[entry_idx]
        self._open_edit_dialog(entry)

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

            # Mitternachts-Splitting beim Bearbeiten
            if dialog.has_times_cb.isChecked() and is_midnight_shift(new_start, new_end):
                p1, p2 = split_midnight_shift(new_date, new_start, new_end)

                # Alten Eintrag löschen
                self.db.delete(entry.id)

                # Zwei neue hinzufügen
                e1 = WorkEntry(
                    id=None, date=p1[0], start=p1[1], end=p1[2],
                    pause=0, minutes=0,
                    reason=dialog.reason_edit.text().strip(),
                    target_minutes=-1
                )
                e2 = WorkEntry(
                    id=None, date=p2[0], start=p2[1], end=p2[2],
                    pause=0, minutes=0,
                    reason=dialog.reason_edit.text().strip(),
                    target_minutes=-1
                )
                self.db.insert(e1)
                self.db.insert(e2)

                affected_dates = [old_date, p1[0], p2[0]]
                QMessageBox.information(
                    self, tr("Mitternachtsschicht"),
                    tr("Der Eintrag wurde auf zwei Tage aufgeteilt:\n"
                       "- {d1}: {s1} - 00:00\n"
                       "- {d2}: 00:00 - {e2}").format(
                           d1=fmt_date(p1[0]), s1=p1[1],
                           d2=fmt_date(p2[0]), e2=p2[2]
                       )
                )
            else:
                dialog.apply_to_entry()
                self.db.update(entry)
                affected_dates = [old_date, entry.date]

            self.entries = self.db.load_all()
            for d in sorted(list(set(affected_dates))):
                self.recalculate_day(d)
            self.data_changed.emit()

    def delete_entry(self, entry):
        """Fragt den Benutzer nach Bestätigung und löscht dann den übergebenen Eintrag."""
        date_str = entry.date
        d = fmt_date(date_str)
        reply = QMessageBox.question(
            self, tr("Löschen bestätigen"),
            tr("Eintrag vom {d} wirklich löschen?").format(d=d),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete(entry.id)
            self.entries = [e for e in self.entries if e.id != entry.id]
            self.recalculate_day(date_str)
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

            for entry in pending:
                self.db.insert(entry)

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
