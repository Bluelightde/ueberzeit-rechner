"""
Überstundenrechner Pro - Ein Tool zur Erfassung und Berechnung von Arbeitsstunden.
"""
import json
import logging
import logging.handlers
import os
import shutil
import sys

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox, QFileDialog
)

# Configuration must be imported before matplotlib for MPLCONFIGDIR
# pylint: disable=wrong-import-position, wrong-import-order
from config import BASE_DIR, DB_FILE, SETTINGS_FILE, ICON_PATH, LOG_FILE
from database import DBManager
from dialogs import SettingsDialog, WelcomeDialog

from i18n import setup_i18n, tr
from tabs.main_tab import MainTab
from tabs.goals_tab import GoalsTab
from tabs.calendar_tab import CalendarTab
from tabs.stats_tab import StatsTab
# pylint: enable=wrong-import-position, wrong-import-order

logger = logging.getLogger(__name__)


def setup_logging():
    """Richtet das App-weite Logging in eine rotierende Log-Datei ein.

    Jede Log-Datei wächst bis zu 1 MB, danach wird sie rotiert (max. 2 Backups).
    Alle Level ab DEBUG werden erfasst — so sind vollständige Diagnosen möglich,
    ohne dass die Dateigröße aus dem Ruder läuft.
    """
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


# --- HAUPTANWENDUNG ---
# pylint: disable=too-many-instance-attributes
class UeberstundenApp(QMainWindow):
    """
    Hauptfenster der Anwendung Überstunden-Rechner Pro.

    Verwaltet die Datenbankverbindung, Einstellungen und das Tab-Layout.
    Die eigentliche UI-Logik liegt in den eigenständigen Tab-Widgets.
    """

    def __init__(self):
        """Initialisiert die Anwendung, lädt Einstellungen und baut die UI auf."""
        super().__init__()
        self.setWindowTitle("Überzeit Rechner")
        self.resize(1000, 750)

        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.system_palette = QApplication.instance().palette()
        bg_color = self.system_palette.color(QPalette.ColorRole.Window)
        self.system_is_dark = bg_color.lightness() < 128

        self.settings = self.load_settings()
        self.db = DBManager(self._resolve_db_path())

        self.apply_theme()

        # Tab-Widgets erstellen und mit gemeinsamen Ressourcen verknüpfen
        self.tab_main = MainTab(
            db=self.db,
            settings=self.settings,
            save_settings_cb=self.save_settings,
            open_settings_cb=self.open_settings,
        )
        self.tab_goals = GoalsTab(
            settings=self.settings,
            save_settings_cb=self.save_settings,
        )
        self.tab_calendar = CalendarTab(settings=self.settings)
        self.tab_stats = StatsTab(settings=self.settings)

        tabs = QTabWidget()
        tabs.addTab(self.tab_main,     tr("Eingabe && Liste"))
        tabs.addTab(self.tab_goals,    tr("Ziele && Dashboard"))
        tabs.addTab(self.tab_calendar, tr("Kalender-Heatmap"))
        tabs.addTab(self.tab_stats,    tr("Diagramm && Statistik"))
        self.setCentralWidget(tabs)

        # Signals verbinden: Datenänderungen im Haupt-Tab → alle Tabs aktualisieren
        self.tab_main.data_changed.connect(self._on_data_changed)

        # Monatsfilter synchronisieren zwischen Haupt-Tab und Kalender-Tab
        self.tab_main.filter_changed.connect(self.tab_calendar.set_filter)
        self.tab_calendar.filter_changed.connect(self.tab_main.set_filter)

        # Erstmalige Befüllung aller Tabs
        self._on_data_changed()

    # --- Datenbankpfad ---

    def _resolve_db_path(self):
        """
        Gibt den konfigurierten DB-Pfad zurück. Wenn das Verzeichnis nicht existiert
        oder die Datei nicht erreichbar ist, öffnet sich ein Dialog zur Auswahl.
        """
        db_path = self.settings.get("db_path", DB_FILE)
        if os.path.exists(db_path):
            return db_path
        if db_path == DB_FILE:
            return db_path
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("Datenbank nicht gefunden"))
        msg.setText(tr(
            "Die Datenbankdatei wurde nicht gefunden:\n{path}\n\n"
            "Bitte wähle eine vorhandene Datenbankdatei oder einen neuen Speicherort."
        ).format(path=db_path))
        btn_select = msg.addButton(tr("Datei auswählen…"), QMessageBox.ButtonRole.AcceptRole)
        btn_new = msg.addButton(tr("Neu erstellen"), QMessageBox.ButtonRole.ActionRole)
        msg.addButton(tr("Abbrechen"), QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_select:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Datenbankdatei auswählen"), DB_FILE,
                tr("SQLite-Datenbank (*.db);;Alle Dateien (*)")
            )
            if path:
                self.settings["db_path"] = path
                self.save_settings()
                return path
        elif clicked == btn_new:
            path, _ = QFileDialog.getSaveFileName(
                self, tr("Neue Datenbankdatei anlegen"), DB_FILE,
                tr("SQLite-Datenbank (*.db);;Alle Dateien (*)")
            )
            if path:
                self.settings["db_path"] = path
                self.save_settings()
                return path
        self.settings["db_path"] = DB_FILE
        self.save_settings()
        return DB_FILE

    # --- Einstellungen ---

    def load_settings(self):
        """Lädt die Einstellungen aus der JSON-Datei oder gibt Standardwerte zurück."""
        defaults = {
            "default_start": "07:00",
            "target_work_time": "08:00",
            "language": "",
            "country": "DE",
            "state": "TH",
            "break_rules": [
                {"after": 360, "break": 30},
                {"after": 540, "break": 45},
            ],
            "dark_mode": self.system_is_dark,
            "auto_break": True,
            "use_login_time": False,
            "workdays": [0, 1, 2, 3, 4],
            "special_days": [
                {"month": 12, "day": 24, "target": "04:00"},
                {"month": 12, "day": 31, "target": "04:00"}
            ],
            "goal_active": False,
            "goal_start_date": QDate.currentDate().addDays(30).toString("yyyy-MM-dd"),
            "goal_end_date": QDate.currentDate().addDays(35).toString("yyyy-MM-dd"),
            "goal_hours": 0,
            "db_path": DB_FILE,
            "first_run": True
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Einstellungsdatei konnte nicht gelesen werden, "
                               "Standardwerte werden verwendet: %s", exc)
        return defaults

    def save_settings(self):
        """Speichert die aktuellen Einstellungen in die JSON-Datei."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
        except OSError as exc:
            logger.error("Einstellungen konnten nicht gespeichert werden: %s", exc)

    # --- Theme ---

    def get_light_palette(self):
        """Erstellt und gibt die Farbpalette für den hellen Modus zurück (Breeze Light)."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.Base,            QColor("#fcfcfc"))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Text,            QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.Button,          QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor("#ff0000"))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor("#3daee9"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Link,            QColor("#3daee9"))
        return palette

    def get_dark_palette(self):
        """Erstellt und gibt die Farbpalette für den dunklen Modus zurück (Breeze Dark)."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor("#232629"))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Base,            QColor("#1b1e20"))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#232629"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Text,            QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Button,          QColor("#232629"))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor("#ff5555"))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor("#3daee9"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Link,            QColor("#3daee9"))
        return palette

    def get_dark_stylesheet(self, icon_dir=''):
        """Gibt das CSS-Stylesheet für den Breeze Dark Modus zurück."""
        return """
            * { font-size: 13px; }

            QMainWindow, QDialog { background-color: #232629; }

            QWidget { background-color: #232629; color: #eff0f1; }

            QPushButton {
                background-color: #3b4045;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 6px 16px;
                min-height: 24px;
            }
            QPushButton:hover  { background-color: #4d5560; border-color: #3daee9; }
            QPushButton:pressed { background-color: #3daee9; color: #fff; border-color: #3daee9; }
            QPushButton:disabled { color: #6c7176; border-color: #3a3f44; }

            QLineEdit, QComboBox {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
                selection-background-color: #3daee9;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3daee9; }

            QAbstractSpinBox {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
            }
            QAbstractSpinBox:focus { border-color: #3daee9; }
            QAbstractSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                background-color: #3b4045;
                border-left: 1px solid #4a5056;
                border-bottom: 1px solid #4a5056;
                border-top-right-radius: 3px;
            }
            QAbstractSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                background-color: #3b4045;
                border-left: 1px solid #4a5056;
                border-bottom-right-radius: 3px;
            }
            QAbstractSpinBox::up-button:hover,
            QAbstractSpinBox::down-button:hover { background-color: #3daee9; }

            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox::down-arrow { width: 10px; height: 10px; }
            QComboBox QAbstractItemView {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
                selection-background-color: #3daee9;
                selection-color: #fff;
                outline: none;
            }

            QTabWidget::pane { border: 1px solid #4a5056; top: -1px; }
            QTabBar::tab {
                background-color: #252a2e;
                color: #7f8c8d;
                border: 1px solid #4a5056;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 5px 14px;
                margin-right: 2px;
            }
            QTabBar::tab:selected    { background-color: #232629; color: #eff0f1; border-bottom: 2px solid #3daee9; }
            QTabBar::tab:hover:!selected { background-color: #3b4045; color: #eff0f1; }

            QTableWidget {
                background-color: #1b1e20;
                alternate-background-color: #1f2326;
                color: #eff0f1;
                gridline-color: #3a3f44;
                border: 1px solid #4a5056;
            }
            QTableWidget::item:selected { background-color: #3daee9; color: #fff; }
            QHeaderView::section {
                background-color: #232629;
                color: #eff0f1;
                border: none;
                border-right: 1px solid #4a5056;
                border-bottom: 1px solid #4a5056;
                padding: 4px 8px;
                font-weight: bold;
            }
            QHeaderView::section:first { border-left: none; }

            QGroupBox {
                border: 1px solid #4a5056;
                border-radius: 3px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                color: #3daee9;
                font-weight: bold;
            }

            QScrollBar:vertical { background: #252a2e; width: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:vertical { background: #4a5056; border-radius: 4px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #3daee9; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #252a2e; height: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:horizontal { background: #4a5056; border-radius: 4px; min-width: 24px; }
            QScrollBar::handle:horizontal:hover { background: #3daee9; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QProgressBar {
                border: 1px solid #4a5056;
                border-radius: 3px;
                background-color: #1b1e20;
                text-align: center;
                color: #eff0f1;
                min-height: 16px;
            }
            QProgressBar::chunk { background-color: #3daee9; border-radius: 2px; }

            QLabel { background: transparent; }
            QFrame { background: transparent; }
            QToolTip { background-color: #232629; color: #eff0f1; border: 1px solid #4a5056; }
            QMessageBox { background-color: #232629; }

            /* Aufklappbarer Kalender (QDateEdit-Popup) */
            QCalendarWidget {
                background-color: #232629;
                color: #eff0f1;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1b1e20;
                padding: 2px;
            }
            QCalendarWidget QToolButton {
                background-color: #3b4045;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 3px 8px;
                margin: 2px;
            }
            QCalendarWidget QToolButton:hover  { background-color: #3daee9; border-color: #3daee9; }
            QCalendarWidget QToolButton:pressed { background-color: #2980b9; }
            QCalendarWidget QToolButton::menu-indicator { image: none; }
            QCalendarWidget QSpinBox {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 2px 4px;
                selection-background-color: #3daee9;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #1b1e20;
                color: #eff0f1;
                selection-background-color: #3daee9;
                selection-color: #ffffff;
                gridline-color: #3a3f44;
            }
            QCalendarWidget QAbstractItemView:disabled { color: #4a5056; }
            QCalendarWidget QMenu {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
            }
            QCalendarWidget QMenu::item:selected { background-color: #3daee9; color: #fff; }
        """ + (
            f"            QAbstractSpinBox::up-arrow   "
            f"{{ image: url(\"{icon_dir}/arrow_up.svg\");   width: 12px; height: 12px; }}\n"
            f"            QAbstractSpinBox::down-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_down.svg\"); width: 12px; height: 12px; }}\n"
            if icon_dir else ""
        )

    def get_light_stylesheet(self, icon_dir=''):
        """Gibt das CSS-Stylesheet für den Breeze Light Modus zurück."""
        return """
            * { font-size: 13px; }

            QMainWindow, QDialog { background-color: #eff0f1; }

            QWidget { background-color: #eff0f1; color: #31363b; }

            QPushButton {
                background-color: #e3e5e7;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 4px 16px;
                min-height: 24px;
            }
            QPushButton:hover  { background-color: #d6eaf8; border-color: #3daee9; }
            QPushButton:pressed { background-color: #3daee9; color: #fff; border-color: #3daee9; }
            QPushButton:disabled { color: #95a5a6; border-color: #bdc3c7; }

            QLineEdit, QComboBox {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
                selection-background-color: #3daee9;
                selection-color: #fff;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3daee9; }

            QAbstractSpinBox {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
            }
            QAbstractSpinBox:focus { border-color: #3daee9; }
            QAbstractSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                background-color: #e3e5e7;
                border-left: 1px solid #bdc3c7;
                border-bottom: 1px solid #bdc3c7;
                border-top-right-radius: 3px;
            }
            QAbstractSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                background-color: #e3e5e7;
                border-left: 1px solid #bdc3c7;
                border-bottom-right-radius: 3px;
            }
            QAbstractSpinBox::up-button:hover,
            QAbstractSpinBox::down-button:hover { background-color: #3daee9; }

            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox::down-arrow { width: 10px; height: 10px; }
            QComboBox QAbstractItemView {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
                selection-background-color: #3daee9;
                selection-color: #fff;
                outline: none;
            }

            QTabWidget::pane { border: 1px solid #bdc3c7; top: -1px; }
            QTabBar::tab {
                background-color: #dde1e3;
                color: #7f8c8d;
                border: 1px solid #bdc3c7;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 5px 14px;
                margin-right: 2px;
            }
            QTabBar::tab:selected    { background-color: #eff0f1; color: #31363b; border-bottom: 2px solid #3daee9; }
            QTabBar::tab:hover:!selected { background-color: #e8eaeb; color: #31363b; }

            QTableWidget {
                background-color: #fcfcfc;
                alternate-background-color: #f4f5f5;
                color: #31363b;
                gridline-color: #d5d8db;
                border: 1px solid #bdc3c7;
            }
            QTableWidget::item:selected { background-color: #3daee9; color: #fff; }
            QHeaderView::section {
                background-color: #e8eaeb;
                color: #31363b;
                border: none;
                border-right: 1px solid #bdc3c7;
                border-bottom: 1px solid #bdc3c7;
                padding: 4px 8px;
                font-weight: bold;
            }

            QGroupBox {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                color: #3daee9;
                font-weight: bold;
            }

            QScrollBar:vertical { background: #dde1e3; width: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:vertical { background: #bdc3c7; border-radius: 4px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #3daee9; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #dde1e3; height: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:horizontal { background: #bdc3c7; border-radius: 4px; min-width: 24px; }
            QScrollBar::handle:horizontal:hover { background: #3daee9; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: #dde1e3;
                text-align: center;
                color: #31363b;
                min-height: 16px;
            }
            QProgressBar::chunk { background-color: #3daee9; border-radius: 2px; }

            QLabel { background: transparent; }
            QFrame { background: transparent; }
            QToolTip { background-color: #31363b; color: #eff0f1; border: 1px solid #4a5056; }

            /* Aufklappbarer Kalender (QDateEdit-Popup) */
            QCalendarWidget {
                background-color: #eff0f1;
                color: #31363b;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #dde1e3;
                padding: 2px;
            }
            QCalendarWidget QToolButton {
                background-color: #e3e5e7;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 3px 8px;
                margin: 2px;
            }
            QCalendarWidget QToolButton:hover  { background-color: #3daee9; color: #fff; border-color: #3daee9; }
            QCalendarWidget QToolButton:pressed { background-color: #2980b9; color: #fff; }
            QCalendarWidget QToolButton::menu-indicator { image: none; }
            QCalendarWidget QSpinBox {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 2px 4px;
                selection-background-color: #3daee9;
                selection-color: #fff;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #fcfcfc;
                color: #31363b;
                selection-background-color: #3daee9;
                selection-color: #ffffff;
                gridline-color: #d5d8db;
            }
            QCalendarWidget QAbstractItemView:disabled { color: #95a5a6; }
            QCalendarWidget QMenu {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
            }
            QCalendarWidget QMenu::item:selected { background-color: #3daee9; color: #fff; }
        """ + (
            f"            QAbstractSpinBox::up-arrow   "
            f"{{ image: url(\"{icon_dir}/arrow_up.svg\");   width: 12px; height: 12px; }}\n"
            f"            QAbstractSpinBox::down-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_down.svg\"); width: 12px; height: 12px; }}\n"
            if icon_dir else ""
        )

    def _create_arrow_icons(self):
        """Erzeugt SVG-Chevron-Pfeile für die QSS-Nutzung (verlustfrei skalierbar)."""
        icon_dir = os.path.join(BASE_DIR, '.ui_icons')
        os.makedirs(icon_dir, exist_ok=True)
        is_dark = self.settings.get("dark_mode", False)
        color = "#eff0f1" if is_dark else "#31363b"
        arrows = {
            'up':   'M2,8 L6,3 L10,8',
            'down': 'M2,4 L6,9 L10,4',
        }
        for name, path in arrows.items():
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
                f'<path d="{path}" stroke="{color}" stroke-width="1.8" '
                f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'</svg>'
            )
            with open(os.path.join(icon_dir, f'arrow_{name}.svg'), 'w', encoding='utf-8') as f:
                f.write(svg)
        return icon_dir.replace('\\', '/')

    def apply_theme(self):
        """Wendet das aktuelle Theme (Hell/Dunkel) auf die gesamte Anwendung an."""
        qt_app = QApplication.instance()
        is_dark = self.settings.get("dark_mode", False)

        if not getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            qt_app.setStyle("Breeze")
            qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
            return

        qt_app.setStyle("Fusion")
        qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
        icon_dir = self._create_arrow_icons()
        sheet = (
            self.get_dark_stylesheet(icon_dir) if is_dark else self.get_light_stylesheet(icon_dir)
        )
        qt_app.setStyleSheet(sheet)

    # --- Daten-Orchestrierung ---

    def _on_data_changed(self):
        """Lädt alle Einträge aus der DB und verteilt sie an alle Tab-Widgets."""
        entries = self.db.load_all()
        self.tab_main.refresh(entries)
        self.tab_goals.refresh(entries)
        self.tab_calendar.refresh(entries)
        self.tab_stats.refresh(entries)

    # --- Einstellungs-Dialog ---

    def open_settings(self):
        """Öffnet den Einstellungs-Dialog und übernimmt geänderte Einstellungen."""
        old_db_path = self.settings.get("db_path", DB_FILE)
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            new_settings = dialog.get_settings()
            new_db_path = new_settings.get("db_path", DB_FILE)

            if new_db_path != old_db_path:
                if os.path.exists(old_db_path) and not os.path.exists(new_db_path):
                    reply = QMessageBox.question(
                        self, tr("Datenbank verschieben?"),
                        tr(
                            "Soll die bestehende Datenbank an den neuen Ort verschoben werden?\n"
                            "(Bei 'Nein' wird am neuen Ort eine neue, leere Datenbank erstellt.)"
                        ),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return
                    if reply == QMessageBox.StandardButton.Yes:
                        try:
                            shutil.move(old_db_path, new_db_path)
                        except OSError as e:
                            QMessageBox.critical(self, tr("Fehler"),
                                tr("Datenbank konnte nicht verschoben werden:\n{e}").format(e=e))
                            return

                self.db.close()
                self.db = DBManager(new_db_path)
                self.tab_main.set_db(self.db)

            self.settings.update(new_settings)
            self.save_settings()
            self.apply_theme()

            # Alle Tage neu berechnen, da sich das Soll geändert haben könnte
            self.tab_main.entries = self.db.load_all()
            self.tab_main.recalculate_all_days()

            # Tabs über Einstellungsänderung informieren und UI neu laden
            self.tab_main.on_settings_changed()
            # Filter zurücksetzen, damit alle Einträge sichtbar sind
            self.tab_main.set_filter("ALL")
            self._on_data_changed()

    # --- Lebenszyklus ---

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Wird beim Schließen der Anwendung aufgerufen. Speichert Einstellungen und DB."""
        self.save_settings()
        self.db.close()
        super().closeEvent(event)


if __name__ == "__main__":
    setup_logging()
    logger.info("Anwendung gestartet")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    # Einstellungen früh laden um gespeicherte Sprache zu kennen
    _early_settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as _f:
                _early_settings = json.load(_f)
        except Exception:  # pylint: disable=broad-except
            pass
    setup_i18n(_early_settings.get("language"))
    window = UeberstundenApp()
    window.show()

    if window.settings.get("first_run", True):
        dlg = WelcomeDialog(window.settings, window)
        if dlg.exec():
            window.settings.update(dlg.get_settings())
            window.tab_main.on_settings_changed()
            window.tab_main.recalculate_all_days()
            window._on_data_changed()
        window.settings["first_run"] = False
        window.save_settings()

    sys.exit(app.exec())
