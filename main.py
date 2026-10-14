"""
Überzeit-Rechner - Ein Tool zur Erfassung und Berechnung von Arbeitsstunden.
"""
import json
import logging
import logging.handlers
import os
import shutil
import sqlite3
import sys
import threading

from PyQt6.QtCore import QDate, QLibraryInfo, QObject, Qt, QTimer, QTranslator, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox, QFileDialog, QPushButton, QWidget
)

# Configuration must be imported before matplotlib for MPLCONFIGDIR
# pylint: disable=wrong-import-position, wrong-import-order
from config import APP_VERSION, BASE_DIR, DB_FILE, SETTINGS_FILE, ICON_PATH, LOG_FILE
from database import DBManager
from dialogs import SettingsDialog, WelcomeDialog

from i18n import current_language, setup_i18n, tr
import server_sync
import updater
from tabs.main_tab import MainTab
from tabs.goals_tab import GoalsTab
from tabs.calendar_tab import CalendarTab
from tabs.bereitschaft_tab import BereitschaftTab
from tabs.session_tab import SessionTab
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
class _UpdateBote(QObject):
    """Bringt Ergebnisse aus dem Update-Thread in den GUI-Thread."""
    fertig = pyqtSignal(object, str, bool)     # Info oder None, Fehlertext, manuell gesucht
    stand = pyqtSignal(str)                    # Fortschritt für die Statusleiste


class UeberstundenApp(QMainWindow):
    """
    Hauptfenster der Anwendung Überzeit-Rechner.

    Verwaltet die Datenbankverbindung, Einstellungen und das Tab-Layout.
    Die eigentliche UI-Logik liegt in den eigenständigen Tab-Widgets.
    """

    def __init__(self):
        """Initialisiert die Anwendung, lädt Einstellungen und baut die UI auf."""
        super().__init__()
        self.setWindowTitle("Überzeit Rechner")
        self.resize(1240, 760)

        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.system_is_dark = self._system_is_dark()

        self.settings = self.load_settings()
        self.db = DBManager(self._resolve_db_path())
        self._auto_backup_on_start()

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
        # StatsTab wird lazy geladen: Erst beim ersten Tab-Klick wird
        # matplotlib importiert und StatsTab konstruiert. Spart ~200-500 ms
        # Startup-Zeit (matplotlib-Import + canvas.draw der 3 Diagramme).
        self.tab_stats = None
        self.tab_bereitschaft = BereitschaftTab(db=self.db)
        self.tab_session = SessionTab(db=self.db)

        tabs = QTabWidget()
        tabs.addTab(self.tab_main,         tr("Eingabe && Liste"))
        tabs.addTab(self.tab_goals,        tr("Ziele && Dashboard"))
        tabs.addTab(self.tab_calendar,     tr("Kalender-Heatmap"))
        tabs.addTab(self.tab_bereitschaft, tr("Bereitschaft"))
        tabs.addTab(self.tab_session,    tr("Anwesenheit"))
        self._stats_placeholder = QWidget()
        self._stats_tab_index = tabs.addTab(self._stats_placeholder, tr("Diagramm && Statistik"))
        # Wichtig: connect erst NACH allen addTab-Aufrufen — sonst feuert das
        # implizite currentChanged(0) beim ersten addTab bereits auf den Handler.
        # Die Lazy-Optimierung hängt davon ab, dass die App immer auf Tab 0
        # startet. Sollte jemals eine "letzten Tab wiederherstellen"-Funktion
        # hinzukommen, müsste _ensure_stats_tab erst nach window.show()
        # scharfgeschaltet werden (z.B. via QTimer.singleShot(0, ...)).
        tabs.currentChanged.connect(self._ensure_stats_tab)
        self.setCentralWidget(tabs)

        # Signals verbinden: Datenänderungen im Haupt-Tab → alle Tabs aktualisieren
        self.tab_main.data_changed.connect(self._on_data_changed)
        self.tab_bereitschaft.data_changed.connect(self._on_data_changed)

        # Monatsfilter synchronisieren zwischen Haupt-Tab und Kalender-Tab
        self.tab_main.filter_changed.connect(self.tab_calendar.set_filter)
        self.tab_calendar.filter_changed.connect(self.tab_main.set_filter)

        # System-Theme live folgen (nur im Automatik-Modus)
        try:
            QApplication.instance().styleHints().colorSchemeChanged.connect(
                self._on_system_color_scheme_changed
            )
        except (AttributeError, TypeError):
            pass  # ältere Qt-Version ohne colorSchemeChanged-Signal

        # Erstmalige Befüllung aller Tabs
        self._on_data_changed()
        # System-Sessions asynchron abfragen, damit der Start nicht auf
        # journalctl/last-Subprocesses wartet (~70 ms warm, kalt deutlich mehr).
        QTimer.singleShot(0, self._sync_system_sessions)

        # Anwesenheit an die Server-Version melden: jetzt und alle 30 Minuten (neue Logins/Logouts)
        self.server_status = ""
        self._anwesenheit_melden()
        self._melde_timer = QTimer(self)
        self._melde_timer.timeout.connect(self._sync_und_melden)
        self._melde_timer.start(30 * 60 * 1000)

        # Updates: kurz nach dem Start und alle 6 Stunden auf GitHub suchen, im Hintergrund laden;
        # installiert wird beim Beenden oder per „Jetzt neu starten“
        self._update_ordner = os.path.join(BASE_DIR, ".update")
        self._update_info = None
        self._update_bereit = False
        self._update_neustart = False
        self._update_laeuft = False
        self.update_status = ""
        self._update_bote = _UpdateBote(self)
        self._update_bote.fertig.connect(self._update_ergebnis)
        self._update_bote.stand.connect(self._update_stand)
        self._update_knopf = QPushButton()
        self._update_knopf.clicked.connect(self._update_knopf_geklickt)
        self.statusBar().addPermanentWidget(self._update_knopf)
        self.statusBar().setVisible(False)
        self._update_nach_start()
        QTimer.singleShot(8000, self._update_pruefen)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_pruefen)
        self._update_timer.start(6 * 60 * 60 * 1000)

    def _sync_und_melden(self):
        self._sync_system_sessions()
        self._anwesenheit_melden()

    def _anwesenheit_melden(self):
        """Schickt die Anwesenheit (device_login) an die Server-Version, falls eingerichtet.

        Gelesen wird hier im GUI-Thread (SQLite-Verbindung), gesendet im Hintergrund – ein langsamer
        oder fehlender Server hält die App nie auf. Fehler landen nur im Protokoll und im Status."""
        if not self.settings.get("server_sync"):
            return
        adresse = self.settings.get("server_url", "")
        token = self.settings.get("server_token", "")
        try:
            from logic import get_login_time
            heute = QDate.currentDate().toString("yyyy-MM-dd")
            login = get_login_time()
            tage = server_sync.tage_auswaehlen(
                self.db.load_all_device_logins(), heute,
                login.toString("HH:mm") if login and login.isValid() else None)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Anwesenheit konnte nicht gelesen werden: %s", exc)
            return

        def senden():
            try:
                anzahl = server_sync.anwesenheit_senden(adresse, token, tage)
                self.server_status = tr("Zuletzt gemeldet: {n} Tage").format(n=anzahl)
                logger.info("Anwesenheit an die Server-Version gemeldet: %s Tage", anzahl)
            except server_sync.ServerFehler as exc:
                self.server_status = str(exc)
                logger.warning("Anwesenheit nicht gemeldet: %s", exc)

        threading.Thread(target=senden, name="anwesenheit-melden", daemon=True).start()

    # --- Updates ---

    def _update_nach_start(self):
        """Meldet das Ergebnis eines Updates beim letzten Beenden und räumt dessen Reste weg."""
        erwartet = self.settings.pop("update_erwartet", None)
        if erwartet:
            self.save_settings()
            if updater.version_tupel(APP_VERSION) >= updater.version_tupel(erwartet):
                logger.info("Update auf %s installiert", APP_VERSION)
                self.statusBar().setVisible(True)
                self.statusBar().showMessage(
                    tr("Auf Version {v} aktualisiert.").format(v=APP_VERSION), 30000)
                QTimer.singleShot(30000, self._statusleiste_anpassen)
            else:
                log = os.path.join(self._update_ordner, "update.log")
                log = log if os.path.exists(log) else LOG_FILE
                logger.error("Update auf %s nicht installiert, es läuft %s", erwartet, APP_VERSION)
                text = tr("Das Update auf Version {v} hat nicht geklappt, "
                          "Version {a} läuft weiter.\nDetails im Protokoll ({p}).").format(
                              v=erwartet, a=APP_VERSION, p=log)
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, tr("Update"), text))
        if getattr(sys, "frozen", False):
            updater.aufraeumen(self._update_ordner)

    def _update_pruefen(self, manuell=False):
        """Sucht im Hintergrund nach einer neueren Version und lädt sie, wenn möglich, gleich."""
        if self._update_bereit:
            if manuell:
                self._update_fragen()
            return
        if self._update_laeuft or not (manuell or self.settings.get("update_auto", True)):
            return
        self._update_laeuft = True
        darf, grund = updater.kann_installieren(BASE_DIR)
        if manuell:
            self._update_stand(tr("Suche nach Updates …"))
        bote, ordner = self._update_bote, self._update_ordner

        def arbeiten():
            info, fehler = None, ""
            try:
                info = updater.suchen(APP_VERSION)
                if info and info["paket"] and darf:
                    zuletzt = [-1]

                    def fortschritt(geladen, gesamt):
                        prozent = int(geladen * 100 / gesamt) if gesamt else 0
                        if prozent // 5 != zuletzt[0]:
                            zuletzt[0] = prozent // 5
                            bote.stand.emit(tr("Update {v} wird geladen: {p} %").format(
                                v=info["version"], p=prozent))

                    archiv = updater.herunterladen(info["paket"], ordner, fortschritt)
                    bote.stand.emit(tr("Update {v} wird ausgepackt …").format(v=info["version"]))
                    updater.auspacken(archiv, ordner)
                    info["bereit"] = True
                elif info:
                    info["grund"] = grund if info["paket"] else updater.KEIN_PAKET
            except updater.UpdateFehler as exc:
                fehler = str(exc)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Update fehlgeschlagen")
                fehler = str(exc)
            bote.fertig.emit(info, fehler, manuell)

        threading.Thread(target=arbeiten, name="update", daemon=True).start()

    def _update_stand(self, text):
        self.statusBar().setVisible(True)
        self.statusBar().showMessage(text)

    def _statusleiste_anpassen(self):
        """Statusleiste nur zeigen, solange sie etwas zu sagen hat."""
        self._update_knopf.setVisible(self._update_info is not None)
        self.statusBar().setVisible(self._update_info is not None
                                    or bool(self.statusBar().currentMessage()))

    def _update_ergebnis(self, info, fehler, manuell):
        self._update_laeuft = False
        self.statusBar().clearMessage()
        if fehler:
            logger.warning("Update: %s", fehler)
        if not info:
            self.update_status = fehler or tr("Version {v} ist aktuell.").format(v=APP_VERSION)
            self._statusleiste_anpassen()
            if manuell:
                if fehler:
                    QMessageBox.warning(self, tr("Update"), fehler)
                else:
                    QMessageBox.information(self, tr("Update"), self.update_status)
            return
        neu_gefunden = self._update_info is None or self._update_info["version"] != info["version"]
        self._update_info = info
        if info.get("bereit"):
            logger.info("Update %s heruntergeladen", info["version"])
            self._update_bereit = True
            self.update_status = tr(
                "Version {v} ist heruntergeladen und wird beim Beenden installiert.").format(
                    v=info["version"])
            self._update_knopf.setText(
                tr("Update {v}: jetzt neu starten").format(v=info["version"]))
            self._statusleiste_anpassen()
            self._update_fragen()
            return
        self.update_status = tr("Version {v} ist verfügbar.").format(v=info["version"])
        grund = fehler or info.get("grund")
        if grund:
            self.update_status += " " + tr(grund)
        self._update_knopf.setText(
            tr("Version {v} verfügbar – herunterladen").format(v=info["version"]))
        self._statusleiste_anpassen()
        if manuell or neu_gefunden:
            logger.info("Neue Version %s verfügbar (%s)", info["version"], grund or "")
        if manuell:
            self._update_knopf_geklickt()

    def _update_fragen(self):
        """Fragt, ob die heruntergeladene Version jetzt installiert werden soll."""
        info = self._update_info
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("Update verfügbar"))
        box.setText(tr("Version {v} ist heruntergeladen (installiert ist {a}).\n\n"
                       "Jetzt neu starten und installieren? Sonst wird sie beim Beenden "
                       "installiert; deine Daten bleiben erhalten.").format(
                           v=info["version"], a=APP_VERSION))
        if info.get("notizen"):
            box.setDetailedText(info["notizen"])
        btn_jetzt = box.addButton(tr("Jetzt neu starten"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Später"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is btn_jetzt:
            self._update_neustart = True
            self.close()

    def _update_knopf_geklickt(self):
        if self._update_bereit:
            self._update_neustart = True
            self.close()
        elif self._update_info:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle(tr("Update verfügbar"))
            box.setText(self.update_status + "\n\n" + tr("Die Download-Seite öffnen?"))
            if self._update_info.get("notizen"):
                box.setDetailedText(self._update_info["notizen"])
            box.setStandardButtons(QMessageBox.StandardButton.Open
                                   | QMessageBox.StandardButton.Close)
            if box.exec() == QMessageBox.StandardButton.Open:
                QDesktopServices.openUrl(QUrl(self._update_info["seite"]))

    def _update_installieren(self):
        """Beim Beenden: heruntergeladenes Update einspielen (Einstellungen gespeichert, DB zu)."""
        self.settings["update_erwartet"] = self._update_info["version"]
        self.save_settings()
        try:
            updater.installieren(self._update_ordner, BASE_DIR, self._update_neustart)
        except (updater.UpdateFehler, OSError) as exc:
            logger.error("Update nicht installiert: %s", exc)
            self.settings.pop("update_erwartet", None)
            self.save_settings()
            QMessageBox.warning(self, tr("Update"),
                                tr("Update nicht installiert: {e}").format(e=exc))

    def _sync_system_sessions(self):
        """Liest Login/Logout-Sessions aus den System-Protokollen und
        füllt die Anwesenheits-Historie nach.

        Die Daten stammen aus journalctl/last – nicht aus der App selbst.
        So werden auch Tage erfasst, an denen die App nicht lief.
        Pro Tag gilt: früher Login bleibt erhalten, später Logout gewinnt.
        """
        try:
            from logic import get_system_sessions
            sessions = get_system_sessions()
            if not sessions:
                return
            for s in sessions:
                date_str = s["date"]
                login_str = s.get("login", "")
                logout_str = s.get("logout", "")
                # Login nur setzen, wenn heute noch keiner existiert
                # (frühester Login gewinnt) oder der bestehende leer ist.
                if login_str:
                    existing = self.db.get_device_login(date_str)
                    if existing is None:
                        self.db.set_device_login(date_str, login_str)
                # Logout setzen / aktualisieren (spätester gewinnt)
                if logout_str:
                    self.db.set_device_logout(date_str, logout_str)
            self.tab_session.refresh_from_db()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("System-Sessions konnten nicht synchronisiert werden: %s", exc)

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

    # --- Backup ---

    def _backup_dir(self):
        """Backup-Ordner neben der aktiven Datenbank-Datei."""
        db_path = os.path.abspath(self.settings.get("db_path", DB_FILE))
        return os.path.join(os.path.dirname(db_path), "backups")

    def _auto_backup_on_start(self):
        """Legt beim Start ein rotierendes Backup an; Fehler blockieren den Start nicht."""
        try:
            self.db.create_backup(self._backup_dir())
        except (OSError, sqlite3.Error) as exc:
            logger.warning("Automatisches Start-Backup fehlgeschlagen: %s", exc)

    def create_manual_backup(self):
        """Erstellt ein Backup on demand; gibt den Pfad zurück oder None bei Fehler."""
        try:
            return self.db.create_backup(self._backup_dir())
        except (OSError, sqlite3.Error) as exc:
            logger.error("Backup fehlgeschlagen: %s", exc)
            return None

    def restore_backup(self, src_path):
        """Stellt die DB aus einem Backup wieder her und lädt alle Tabs neu.
        Gibt True bei Erfolg zurück, sonst False."""
        try:
            self.db.restore_from(src_path)
        except (OSError, sqlite3.Error) as exc:
            logger.error("Wiederherstellung fehlgeschlagen: %s", exc)
            return False
        self.tab_main.entries = self.db.load_all()
        self.tab_main.recalculate_all_days()
        self.tab_main.on_settings_changed()
        self._on_data_changed()
        return True

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
            "theme": "auto",
            "dark_mode": self.system_is_dark,
            "auto_break": True,
            "use_login_time": True,
            "is_primary_device": False,
            "bereitschaft_color": "#eab308",
            "type_colors": {
                "vacation": "#06b6d4",
                "sick": "#f97316",
                "holiday": "#a855f7",
                "flextime": "#84cc16",
                "parental": "#ec4899",
            },
            "workdays": [0, 1, 2, 3, 4],
            "vacation_entitlement": 30,
            "special_days": [
                {"month": 12, "day": 24, "target": "04:00"},
                {"month": 12, "day": 31, "target": "04:00"}
            ],
            "goal_active": False,
            "goal_start_date": QDate.currentDate().addDays(30).toString("yyyy-MM-dd"),
            "goal_end_date": QDate.currentDate().addDays(35).toString("yyyy-MM-dd"),
            "goal_hours": 0,
            "db_path": DB_FILE,
            "update_auto": True,
            "first_run": True
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("Einstellungsdatei konnte nicht gelesen werden, "
                               "Standardwerte werden verwendet: %s", exc)
            else:
                if isinstance(loaded, dict):
                    defaults.update(loaded)
                else:
                    logger.warning("Einstellungsdatei enthält kein JSON-Objekt (%s), "
                                   "Standardwerte werden verwendet.",
                                   type(loaded).__name__)
        # Per-Wochentag-Soll ableiten, falls (noch) nicht vorhanden
        # (alte Einstellungen kennen nur workdays + target_work_time).
        weekday_targets = defaults.get("weekday_targets")
        if not (isinstance(weekday_targets, list) and len(weekday_targets) == 7):
            tw = defaults.get("target_work_time", "08:00")
            wd = defaults.get("workdays", [0, 1, 2, 3, 4])
            defaults["weekday_targets"] = [tw if i in wd else "" for i in range(7)]
        return defaults

    def save_settings(self):
        """Speichert die aktuellen Einstellungen atomar in die JSON-Datei."""
        tmp_file = SETTINGS_FILE + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
            os.replace(tmp_file, SETTINGS_FILE)
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
        for _role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                      QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, _role, QColor("#95a5a6"))
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
        for _role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                      QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, _role, QColor("#6c7176"))
        return palette

    def get_dark_stylesheet(self, icon_dir=''):
        """Gibt das CSS-Stylesheet für den Breeze Dark Modus zurück."""
        return """
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
            QPushButton:hover  { border-color: #3daee9; }
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
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #232629; color: #6c7176; border-color: #3a3f44;
            }
            QLabel:disabled, QCheckBox:disabled { color: #6c7176; }

            QAbstractSpinBox {
                background-color: #1b1e20;
                color: #eff0f1;
                border: 1px solid #4a5056;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
            }
            QAbstractSpinBox:focus { border-color: #3daee9; }
            QAbstractSpinBox:disabled {
                background-color: #232629; color: #6c7176; border-color: #3a3f44;
            }
            QAbstractSpinBox::up-button {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                background: transparent;
                border: none;
            }
            QAbstractSpinBox::down-button {
                subcontrol-origin: padding;
                subcontrol-position: bottom right;
                width: 16px;
                background: transparent;
                border: none;
            }

            QDateEdit::drop-down,
            QDateTimeEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 18px;
                background: transparent;
                border: none;
            }

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
        """ + (self._arrow_icons_css(icon_dir) if icon_dir else "")

    def get_light_stylesheet(self, icon_dir=''):
        """Gibt das CSS-Stylesheet für den Breeze Light Modus zurück."""
        return """
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
            QPushButton:hover  { border-color: #3daee9; }
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
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #e8e9ea; color: #95a5a6; border-color: #bdc3c7;
            }
            QLabel:disabled, QCheckBox:disabled { color: #95a5a6; }

            QAbstractSpinBox {
                background-color: #fcfcfc;
                color: #31363b;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 3px 6px;
                min-height: 24px;
            }
            QAbstractSpinBox:focus { border-color: #3daee9; }
            QAbstractSpinBox:disabled {
                background-color: #e8e9ea; color: #95a5a6; border-color: #bdc3c7;
            }
            QAbstractSpinBox::up-button {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                background: transparent;
                border: none;
            }
            QAbstractSpinBox::down-button {
                subcontrol-origin: padding;
                subcontrol-position: bottom right;
                width: 16px;
                background: transparent;
                border: none;
            }

            QDateEdit::drop-down,
            QDateTimeEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 18px;
                background: transparent;
                border: none;
            }

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
        """ + (self._arrow_icons_css(icon_dir) if icon_dir else "")

    def _arrow_icons_css(self, icon_dir):
        """Liefert die QSS-Regeln, die die Pfeil-SVGs für SpinBox- und
        Date-Edit-Subcontrols setzen — inkl. Hover-Variante in Breeze-Blau."""
        return (
            f"            QAbstractSpinBox::up-arrow,\n"
            f"            QDateTimeEdit::up-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_up.svg\"); width: 12px; height: 12px; }}\n"
            f"            QAbstractSpinBox::down-arrow,\n"
            f"            QDateTimeEdit::down-arrow "
            f"{{ image: url(\"{icon_dir}/arrow_down.svg\"); width: 12px; height: 12px; }}\n"
            f"            QAbstractSpinBox::up-arrow:hover,\n"
            f"            QDateTimeEdit::up-arrow:hover "
            f"{{ image: url(\"{icon_dir}/arrow_up_hover.svg\"); }}\n"
            f"            QAbstractSpinBox::down-arrow:hover,\n"
            f"            QDateTimeEdit::down-arrow:hover "
            f"{{ image: url(\"{icon_dir}/arrow_down_hover.svg\"); }}\n"
        )

    def _create_arrow_icons(self):
        """Erzeugt SVG-Chevron-Pfeile für die QSS-Nutzung (verlustfrei skalierbar).

        Pro Richtung werden zwei Varianten geschrieben: die Default-Variante
        (in Textfarbe) und eine ``_hover``-Variante in Breeze-Blau, die per
        ``:hover``-Selector eingeblendet wird.
        """
        icon_dir = os.path.join(BASE_DIR, '.ui_icons')
        os.makedirs(icon_dir, exist_ok=True)
        is_dark = self.settings.get("dark_mode", False)
        default_color = "#eff0f1" if is_dark else "#31363b"
        hover_color = "#3daee9"
        # Flache Chevrons (Höhe 3px im 12x12-viewBox), näher zur Mitte hin
        # positioniert, damit Up/Down im Spinbox optisch enger zusammenrücken.
        arrows = {
            'up':   'M2,9 L6,5 L10,9',
            'down': 'M2,3 L6,7 L10,3',
        }
        variants = {'': default_color, '_hover': hover_color}
        for name, path in arrows.items():
            for suffix, color in variants.items():
                svg = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
                    f'<path d="{path}" stroke="{color}" stroke-width="1.3" '
                    f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                    f'</svg>'
                )
                fname = f'arrow_{name}{suffix}.svg'
                with open(os.path.join(icon_dir, fname), 'w', encoding='utf-8') as f:
                    f.write(svg)
        return icon_dir.replace('\\', '/')

    def _system_is_dark(self):
        """Erkennt das System-Theme – bevorzugt über die Qt-StyleHints
        (Qt ≥ 6.5), mit Palette-Helligkeit als Fallback."""
        app = QApplication.instance()
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except (AttributeError, TypeError):
            pass  # ältere Qt-Version ohne colorScheme()
        bg = app.palette().color(QPalette.ColorRole.Window)
        return bg.lightness() < 128

    def _resolve_dark(self):
        """Löst die theme-Einstellung (auto/light/dark) in den effektiven
        Dunkel-Modus-Bool auf."""
        theme = self.settings.get("theme", "auto")
        if theme == "light":
            return False
        if theme == "dark":
            return True
        return self._system_is_dark()

    def _on_system_color_scheme_changed(self, _scheme):
        """Folgt einem System-Themewechsel live – nur im Automatik-Modus."""
        if self.settings.get("theme", "auto") != "auto":
            return
        if self._system_is_dark() == self.settings.get("dark_mode"):
            return  # keine effektive Änderung
        self.apply_theme()
        self._on_data_changed()  # Charts/Kalender mit neuem Theme neu zeichnen

    def apply_theme(self):
        """Wendet das aktuelle Theme (Hell/Dunkel) auf die gesamte Anwendung an."""
        qt_app = QApplication.instance()
        is_dark = self._resolve_dark()
        self.settings["dark_mode"] = is_dark  # effektiver Wert für Charts/Kalender/Icons

        if not getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            qt_app.setStyle("Breeze")
            qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
            return

        qt_app.setStyle("Fusion")
        qt_app.setPalette(self.get_dark_palette() if is_dark else self.get_light_palette())
        # Default-Schriftgröße per QFont setzen, damit widget.setFont(...) sie
        # überschreiben kann. Ein "* { font-size: ... }" im Stylesheet würde
        # alle per QFont gesetzten PointSizes (z.B. das große Saldo-Label)
        # überschreiben.
        app_font = qt_app.font()
        app_font.setPixelSize(13)
        qt_app.setFont(app_font)
        icon_dir = self._create_arrow_icons()
        sheet = (
            self.get_dark_stylesheet(icon_dir) if is_dark else self.get_light_stylesheet(icon_dir)
        )
        qt_app.setStyleSheet(sheet)

    # --- Daten-Orchestrierung ---

    def _on_data_changed(self):
        """Lädt alle Einträge aus der DB und verteilt sie an alle Tab-Widgets."""
        entries = self.db.load_all()
        bereitschaft = self.db.load_all_bereitschaft()
        self.tab_main.refresh(entries)
        self.tab_goals.refresh(entries)
        self.tab_calendar.refresh(entries, bereitschaft)
        self.tab_bereitschaft.refresh(bereitschaft)
        self.tab_session.refresh(self.db.load_all_device_logins())
        if self.tab_stats is not None:
            self.tab_stats.refresh(entries)
        self._pending_entries = entries

    def _ensure_stats_tab(self, index):
        """Lazy-Initialisierung des Statistik-Tabs beim ersten Sichtbarwerden.

        currentChanged feuert bei jedem Tab-Wechsel — egal ob per Maus,
        Tastatur (Strg+Tab/Pfeiltasten) oder programmatisch. So wird der
        StatsTab (inkl. matplotlib-Import) robust geladen, sobald der Nutzer
        den Statistik-Tab das erste Mal betritt.
        """
        if index != self._stats_tab_index or self.tab_stats is not None:
            return
        from tabs.stats_tab import StatsTab  # noqa: WPS433 — bewusst lazy
        self.tab_stats = StatsTab(settings=self.settings)
        if hasattr(self, "_pending_entries"):
            self.tab_stats.refresh(self._pending_entries)
        tabs = self.centralWidget()
        tabs.removeTab(self._stats_tab_index)
        tabs.insertTab(self._stats_tab_index, self.tab_stats, tr("Diagramm && Statistik"))
        tabs.setCurrentIndex(self._stats_tab_index)

    # --- Einstellungs-Dialog ---

    def open_settings(self):
        """Öffnet den Einstellungs-Dialog und übernimmt geänderte Einstellungen."""
        old_db_path = self.settings.get("db_path", DB_FILE)
        dialog = SettingsDialog(self.settings, self,
                                backup_cb=self.create_manual_backup,
                                restore_cb=self.restore_backup,
                                server_status=self.server_status,
                                update_status=self.update_status,
                                update_cb=lambda: self._update_pruefen(manuell=True))
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
                self.tab_bereitschaft.set_db(self.db)
                self.tab_session.set_db(self.db)

            self.settings.update(new_settings)
            self.save_settings()
            self.apply_theme()
            self._anwesenheit_melden()

            # Alle Tage neu berechnen, da sich das Soll geändert haben könnte
            self.tab_main.entries = self.db.load_all()
            self.tab_main.recalculate_all_days()

            # Tabs über Einstellungsänderung informieren und UI neu laden
            self.tab_main.on_settings_changed()
            self.tab_main.set_filter("ALL")
            self._on_data_changed()

    # --- Lebenszyklus ---

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Wird beim Schließen der Anwendung aufgerufen. Speichert Einstellungen und DB."""
        self.save_settings()
        self.db.close()
        if self._update_bereit:
            self._update_installieren()
        super().closeEvent(event)


def _preload_stats_modules():
    """Wärmt den Modul-Cache für den Statistik-Tab (matplotlib + StatsTab) vor.

    Der Import von ``tabs.stats_tab`` zieht auf Modulebene matplotlib und das
    Qt-Agg-Backend nach — mit Abstand der teuerste Teil beim ersten Öffnen des
    Tabs (~0,6–3 s je nach Datenträger-Cache). Läuft im Hintergrund-Thread und
    führt bewusst NUR Imports aus; die Figure-/Canvas-Konstruktion bleibt dem
    Main-Thread in ``_ensure_stats_tab`` vorbehalten. Ist der Import dort noch
    nicht durch, greift weiterhin der synchrone Fallback — Python serialisiert
    konkurrierende Imports desselben Moduls über den Import-Lock.
    """
    try:
        import tabs.stats_tab  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    except Exception:  # pylint: disable=broad-except  # Preload darf die App nie stören
        logger.debug("StatsTab-Preload fehlgeschlagen", exc_info=True)


def _start_stats_preload():
    """Startet den StatsTab-Modul-Preload in einem Daemon-Thread."""
    threading.Thread(
        target=_preload_stats_modules, name="stats-preload", daemon=True
    ).start()


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

    # Qt-eigene Übersetzungen (z.B. Yes/No in Standard-Dialogen) laden,
    # damit Buttons in QMessageBox/QDialogButtonBox in der App-Sprache erscheinen.
    qt_translator = QTranslator(app)
    qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(f"qtbase_{current_language()}", qt_translations_path):
        app.installTranslator(qt_translator)
    else:
        logger.debug("Qt-Übersetzung für %s nicht gefunden in %s",
                     current_language(), qt_translations_path)

    window = UeberstundenApp()
    window.show()

    # matplotlib + StatsTab-Modul im Hintergrund vorladen, damit der erste
    # Klick auf den Statistik-Tab nicht durch den matplotlib-Import blockiert.
    _start_stats_preload()

    if window.settings.get("first_run", True):
        dlg = WelcomeDialog(window.settings, window)
        if dlg.exec():
            window.settings.update(dlg.get_settings())
            window.tab_main.on_settings_changed()
            window.tab_main.recalculate_all_days()
            window._on_data_changed()  # pylint: disable=protected-access
            window.settings["first_run"] = False
            window.save_settings()

    sys.exit(app.exec())
