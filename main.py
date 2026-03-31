"""
Überstundenrechner Pro - Ein Tool zur Erfassung und Berechnung von Arbeitsstunden.
"""
import json
import os
import shutil
import sys

from PyQt6.QtCore import QDate, Qt, QTime, QPoint
from PyQt6.QtGui import QColor, QIcon, QPalette, QPainter, QPixmap, QPolygon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QMessageBox, QFileDialog
)

# Configuration must be imported before matplotlib for MPLCONFIGDIR
# pylint: disable=wrong-import-position, wrong-import-order
from config import BASE_DIR, DB_FILE, SETTINGS_FILE, ICON_PATH
from database import DBManager
from logic import get_holidays
from dialogs import SettingsDialog

from tabs.main_tab import MainTabMixin
from tabs.goals_tab import GoalsTabMixin
from tabs.calendar_tab import CalendarTabMixin
from tabs.stats_tab import StatsTabMixin
# pylint: enable=wrong-import-position, wrong-import-order


# --- HAUPTANWENDUNG ---
# pylint: disable=too-many-instance-attributes, too-many-public-methods
class UeberstundenApp(QMainWindow, MainTabMixin, GoalsTabMixin, CalendarTabMixin, StatsTabMixin):
    """
    Hauptklasse der Anwendung Überstunden-Rechner Pro.
    Verwaltet das Hauptfenster, die Tabs und die Geschäftslogik.
    """
    def __init__(self):
        """
        Initialisiert die Anwendung, lädt Einstellungen und baut die UI auf.
        """
        super().__init__()
        self.setWindowTitle("Überstunden-Rechner Pro")
        self.resize(1000, 750)

        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.system_palette = QApplication.instance().palette()
        bg_color = self.system_palette.color(QPalette.ColorRole.Window)
        bg_lightness = bg_color.lightness()
        self.system_is_dark = bg_lightness < 128

        self.settings = self.load_settings()
        self.db = DBManager(self._resolve_db_path())

        self.entries = []
        self.current_calculated_overtime = 0
        self.current_calculated_pause = 0

        self.apply_theme()

        # Daten laden BEVOR die UI sie berechnet
        self.entries = self.db.load_all()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_main = QWidget()
        self.tab_goals = QWidget()
        self.tab_calendar = QWidget()
        self.tab_stats = QWidget()

        self.tabs.addTab(self.tab_main, "Eingabe && Liste")
        self.tabs.addTab(self.tab_goals, "Ziele && Dashboard")
        self.tabs.addTab(self.tab_calendar, "Kalender-Heatmap")
        self.tabs.addTab(self.tab_stats, "Diagramm && Statistik")

        self.setup_main_tab()
        self.setup_goals_tab()
        self.setup_calendar_tab()
        self.setup_stats_tab()

        self.load_data()

    def _resolve_db_path(self):
        """
        Gibt den konfigurierten DB-Pfad zurück. Wenn das Verzeichnis nicht existiert
        oder die Datei nicht erreichbar ist, öffnet sich ein Dialog zur Auswahl.
        """
        db_path = self.settings.get("db_path", DB_FILE)
        if os.path.exists(db_path):
            return db_path
        # Wenn es der Standard-Pfad ist, darf sqlite3 eine neue DB anlegen
        if db_path == DB_FILE:
            return db_path
        # Benutzerdefinierter Pfad existiert nicht → nachfragen
        msg = QMessageBox(self)
        msg.setWindowTitle("Datenbank nicht gefunden")
        msg.setText(
            f"Die Datenbankdatei wurde nicht gefunden:\n{db_path}\n\n"
            "Bitte wähle eine vorhandene Datenbankdatei oder einen neuen Speicherort."
        )
        btn_select = msg.addButton("Datei auswählen…", QMessageBox.ButtonRole.AcceptRole)
        btn_new = msg.addButton("Neu erstellen", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_select:
            path, _ = QFileDialog.getOpenFileName(
                self, "Datenbankdatei auswählen", DB_FILE,
                "SQLite-Datenbank (*.db);;Alle Dateien (*)"
            )
            if path:
                self.settings["db_path"] = path
                self.save_settings()
                return path
        elif clicked == btn_new:
            path, _ = QFileDialog.getSaveFileName(
                self, "Neue Datenbankdatei anlegen", DB_FILE,
                "SQLite-Datenbank (*.db);;Alle Dateien (*)"
            )
            if path:
                self.settings["db_path"] = path
                self.save_settings()
                return path
        # Fallback: Standard-Pfad verwenden
        self.settings["db_path"] = DB_FILE
        self.save_settings()
        return DB_FILE

    def load_settings(self):
        """
        Lädt die Einstellungen aus der JSON-Datei oder gibt Standardwerte zurück.
        """
        defaults = {
            "default_start": "07:00",
            "target_work_time": "08:00",
            "state": "TH",
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
            "db_path": DB_FILE
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return defaults

    def save_settings(self):
        """
        Speichert die aktuellen Einstellungen in die JSON-Datei.
        """
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
        except OSError:
            pass

    def get_light_palette(self):
        """
        Erstellt und gibt die Farbpalette für den hellen Modus zurück (Breeze Light).
        """
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
        """
        Erstellt und gibt die Farbpalette für den dunklen Modus zurück (Breeze Dark).
        """
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Base,            QColor("#232629"))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Text,            QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.Button,          QColor("#31363b"))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#eff0f1"))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor("#ff5555"))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor("#3daee9"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Link,            QColor("#3daee9"))
        return palette

    def get_dark_stylesheet(self, icon_dir=''):
        """
        Gibt das CSS-Stylesheet für den Breeze Dark Modus zurück.
        """
        return """
            * { font-size: 13px; }

            QMainWindow, QDialog { background-color: #31363b; }

            QWidget { background-color: #31363b; color: #eff0f1; }

            QPushButton {
                background-color: #3b4045;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 4px 16px;
                min-height: 24px;
            }
            QPushButton:hover  { background-color: #4d5560; border-color: #3daee9; }
            QPushButton:pressed { background-color: #3daee9; color: #fff; border-color: #3daee9; }
            QPushButton:disabled { color: #6c7176; border-color: #3a3f44; }

            QLineEdit, QComboBox {
                background-color: #232629;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
                selection-background-color: #3daee9;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3daee9; }

            QAbstractSpinBox {
                background-color: #232629;
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
                background-color: #232629;
                color: #eff0f1;
                border: 1px solid #4a5056;
                selection-background-color: #3daee9;
                selection-color: #fff;
                outline: none;
            }

            QTabWidget::pane { border: 1px solid #4a5056; top: -1px; }
            QTabBar::tab {
                background-color: #2e3338;
                color: #7f8c8d;
                border: 1px solid #4a5056;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 5px 14px;
                margin-right: 2px;
            }
            QTabBar::tab:selected    { background-color: #31363b; color: #eff0f1; border-bottom: 2px solid #3daee9; }
            QTabBar::tab:hover:!selected { background-color: #3b4045; color: #eff0f1; }

            QTableWidget {
                background-color: #232629;
                alternate-background-color: #2a2f34;
                color: #eff0f1;
                gridline-color: #3a3f44;
                border: 1px solid #4a5056;
            }
            QTableWidget::item:selected { background-color: #3daee9; color: #fff; }
            QHeaderView::section {
                background-color: #31363b;
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

            QCheckBox::indicator {
                width: 16px; height: 16px;
                border: 1px solid #4a5056;
                border-radius: 2px;
                background-color: #232629;
            }
            QCheckBox::indicator:checked  { background-color: #3daee9; border-color: #3daee9; }
            QCheckBox::indicator:hover    { border-color: #3daee9; }

            QScrollBar:vertical { background: #2e3338; width: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:vertical { background: #4a5056; border-radius: 4px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #3daee9; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #2e3338; height: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:horizontal { background: #4a5056; border-radius: 4px; min-width: 24px; }
            QScrollBar::handle:horizontal:hover { background: #3daee9; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QProgressBar {
                border: 1px solid #4a5056;
                border-radius: 3px;
                background-color: #232629;
                text-align: center;
                color: #eff0f1;
                min-height: 16px;
            }
            QProgressBar::chunk { background-color: #3daee9; border-radius: 2px; }

            QLabel { background: transparent; }
            QFrame { background: transparent; }
            QToolTip { background-color: #31363b; color: #eff0f1; border: 1px solid #4a5056; }
            QMessageBox { background-color: #31363b; }

            /* Aufklappbarer Kalender (QDateEdit-Popup) */
            QCalendarWidget {
                background-color: #31363b;
                color: #eff0f1;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #232629;
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
                background-color: #232629;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 2px 4px;
                selection-background-color: #3daee9;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #232629;
                color: #eff0f1;
                selection-background-color: #3daee9;
                selection-color: #ffffff;
                gridline-color: #3a3f44;
            }
            QCalendarWidget QAbstractItemView:disabled { color: #4a5056; }
            QCalendarWidget QMenu {
                background-color: #232629;
                color: #eff0f1;
                border: 1px solid #4a5056;
            }
            QCalendarWidget QMenu::item:selected { background-color: #3daee9; color: #fff; }
        """ + (
            f"            QAbstractSpinBox::up-arrow   "
            f"{{ image: url(\"{icon_dir}/arrow_up.png\");   width: 10px; height: 10px; }}\n"
            f"            QAbstractSpinBox::down-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_down.png\"); width: 10px; height: 10px; }}\n"
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

            QCheckBox::indicator {
                width: 16px; height: 16px;
                border: 1px solid #bdc3c7;
                border-radius: 2px;
                background-color: #fcfcfc;
            }
            QCheckBox::indicator:checked { background-color: #3daee9; border-color: #3daee9; }
            QCheckBox::indicator:hover   { border-color: #3daee9; }

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
            f"{{ image: url(\"{icon_dir}/arrow_up.png\");   width: 10px; height: 10px; }}\n"
            f"            QAbstractSpinBox::down-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_down.png\"); width: 10px; height: 10px; }}\n"
            if icon_dir else ""
        )

    def _create_arrow_icons(self):
        """Zeichnet kleine Dreieck-Pfeile als PNG und speichert sie für die QSS-Nutzung."""
        icon_dir = os.path.join(BASE_DIR, '.ui_icons')
        os.makedirs(icon_dir, exist_ok=True)
        is_dark = self.settings.get("dark_mode", False)
        color = QColor("#eff0f1") if is_dark else QColor("#31363b")
        arrows = {
            'up':   [QPoint(5, 1), QPoint(10, 9), QPoint(0, 9)],
            'down': [QPoint(0, 1), QPoint(10, 1), QPoint(5, 9)],
        }
        for name, pts in arrows.items():
            px = QPixmap(10, 10)
            px.fill(Qt.GlobalColor.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygon(pts))
            p.end()
            px.save(os.path.join(icon_dir, f'arrow_{name}.png'))
        # Qt QSS benötigt Forward-Slashes, auch auf Windows
        return icon_dir.replace('\\', '/')

    def apply_theme(self):
        """Wendet das aktuelle Theme (Hell/Dunkel) auf die gesamte Anwendung an."""
        qt_app = QApplication.instance()
        is_dark = self.settings.get("dark_mode", False)

        # Auf Linux im Entwicklungsmodus: natives Breeze-Theme nutzen
        if not getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            qt_app.setStyle("Breeze")
            qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
            return

        # Alle anderen Fälle (kompiliert oder Windows/macOS): Fusion + modernes Stylesheet
        qt_app.setStyle("Fusion")
        qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
        icon_dir = self._create_arrow_icons()
        sheet = (
            self.get_dark_stylesheet(icon_dir) if is_dark else self.get_light_stylesheet(icon_dir)
        )
        qt_app.setStyleSheet(sheet)

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """
        Wird beim Schließen der Anwendung aufgerufen. Speichert Einstellungen und schließt die DB.
        """
        self.save_settings()
        self.db.close()
        super().closeEvent(event)

    def get_target_minutes(self):
        """
        Gibt die in den Einstellungen festgelegte Regelarbeitszeit in Minuten zurück.
        """
        t = QTime.fromString(self.settings.get("target_work_time", "08:00"), "HH:mm")
        return t.hour() * 60 + t.minute()

    def get_target_minutes_for_date(self, date_str):
        """
        Ermittelt das Tagessoll für ein bestimmtes Datum unter Berücksichtigung von
        individuellen Einträgen, Sonderarbeitstagen, Feiertagen und Wochenenden.
        """
        # 1. Check if any entry for this day has a custom target_minutes
        for e in self.entries:
            if e.date == date_str and e.target_minutes != -1:
                return e.target_minutes

        qdate = QDate.fromString(date_str, "yyyy-MM-dd")

        # 2. Check special days from settings (e.g. 24.12.)
        special_days = self.settings.get("special_days", [])
        for sd in special_days:
            if qdate.month() == sd["month"] and qdate.day() == sd["day"]:
                t = QTime.fromString(sd["target"], "HH:mm")
                return t.hour() * 60 + t.minute()

        year = qdate.year()
        state = self.settings.get("state", "TH")
        holidays = get_holidays(year, state)

        # Check if holiday
        if date_str in holidays:
            return 0

        # Check if workday (0=Mon, 6=Sun)
        # QDate.dayOfWeek() returns 1 (Mon) to 7 (Sun)
        day_idx = qdate.dayOfWeek() - 1
        workdays = self.settings.get("workdays", [0, 1, 2, 3, 4])
        if day_idx not in workdays:
            return 0

        return self.get_target_minutes()

    def get_max_minutes(self):
        """
        Gibt die maximal anrechenbare Arbeitszeit pro Tag in Minuten zurück.
        """
        return self.settings.get("max_work_hours", 10) * 60

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
                        self, "Datenbank verschieben?",
                        "Soll die bestehende Datenbank an den neuen Ort verschoben werden?\n"
                        "(Bei 'Nein' wird am neuen Ort eine neue, leere Datenbank erstellt.)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return
                    if reply == QMessageBox.StandardButton.Yes:
                        try:
                            shutil.move(old_db_path, new_db_path)
                        except OSError as e:
                            QMessageBox.critical(self, "Fehler",
                                               f"Datenbank konnte nicht verschoben werden:\n{e}")
                            return

                self.db.close()
                self.db = DBManager(new_db_path)
                self.entries = self.db.load_all()

            self.settings.update(new_settings)
            self.save_settings()
            self.apply_theme()
            self.pause_spin.setEnabled(not self.settings.get("auto_break", True))

            # Alle Tage neu berechnen, da sich das Soll geändert haben könnte
            all_dates = sorted(list(set(e.date for e in self.entries)))
            for d_str in all_dates:
                self.recalculate_day(d_str)

            self.load_data() # Lädt alles neu (inkl. UI-Update)

            new_start = self._get_default_start_time()
            self.time_start.blockSignals(True)
            self.time_start.setTime(new_start)
            self.time_start.blockSignals(False)
            self.on_start_time_changed(new_start)

    def format_time(self, total_minutes, show_plus=False):
        """Formatiert Minuten in Stunden und Minuten.
        Unter 60 Min -> '45m'
        Ab 60 Min    -> '1h 5m'
        """
        sign = "+" if show_plus and total_minutes > 0 else ("-" if total_minutes < 0 else "")
        abs_m = abs(total_minutes)
        if abs_m < 60:
            return f"{sign}{abs_m}m"
        return f"{sign}{abs_m // 60}h {abs_m % 60}m"


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    window = UeberstundenApp()
    window.show()
    sys.exit(app.exec())
