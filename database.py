
"""
Verwaltung der Datenbankverbindung und -operationen.
"""
import glob
import os
import sqlite3
from datetime import datetime

import kern
from models import WorkEntry, BereitschaftEntry

SCHEMA_VERSION = 4
BACKUP_KEEP = 10

class DBManager:  # pylint: disable=too-many-public-methods
    """
    Verwaltet die SQLite-Datenbankverbindung und Operationen für Arbeits- und
    Bereitschafts-Einträge.
    """
    def __init__(self, db_path):
        """
        Initialisiert den DBManager und erstellt die Tabellen, falls sie nicht existieren.
        """
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        """Erstellt die Tabellen (falls nicht vorhanden) und führt versionierte
        Migrationen aus (siehe `_run_migrations`)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start TEXT,
                end TEXT,
                pause INTEGER,
                minutes INTEGER,
                reason TEXT,
                target_minutes INTEGER DEFAULT -1,
                type TEXT NOT NULL DEFAULT 'work'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bereitschaft_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start TEXT,
                end TEXT,
                note TEXT,
                end_date TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_login (
                date TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT
            )
        """)
        self._run_migrations(cursor)
        self.conn.commit()

    def _run_migrations(self, cursor):
        """Bringt das Schema über `PRAGMA user_version` schrittweise auf
        SCHEMA_VERSION. Migrationsschritte sind idempotent."""
        cursor.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]
        if version >= SCHEMA_VERSION:
            return
        if version < 1:
            # v0 -> v1: Spalten, die früher ad-hoc nachgezogen wurden.
            self._ensure_column(cursor, "entries", "target_minutes",
                                 "INTEGER DEFAULT -1")
            self._ensure_column(cursor, "bereitschaft_entries", "end_date", "TEXT")
        if version < 2:
            # v1 -> v2: Eintragstypen (work/vacation/sick/holiday/flextime)
            self._ensure_column(cursor, "entries", "type",
                                 "TEXT NOT NULL DEFAULT 'work'")
        if version < 3:
            # v2 -> v3: Logout-Zeit (end_time) für Anwesenheits-Übersicht
            self._ensure_column(cursor, "device_login", "end_time", "TEXT")
        if version < 4:
            # v3 -> v4: Abgleich mit der Server-Version (abgleich.py). tag_geaendert: wann ein Tag
            # hier zuletzt geändert wurde (UTC, per Trigger -- egal über welchen Weg).
            # abgleich_stand: Fingerabdruck je Tag beim letzten erfolgreichen Abgleich.
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS tag_geaendert (date TEXT PRIMARY KEY, zeit TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS abgleich_stand (date TEXT PRIMARY KEY, hash TEXT NOT NULL);
            """ + _trigger("entries", "start, end, pause, minutes, reason, target_minutes, type")
                + _trigger("bereitschaft_entries", "start, end, note, end_date"))
        cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _ensure_column(cursor, table, column, decl):
        """Fügt eine Spalte hinzu, falls sie noch nicht existiert (idempotent)."""
        cursor.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cursor.fetchall()]
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def load_all(self):
        """
        Lädt alle Arbeitseinträge aus der Datenbank, sortiert nach Datum und Startzeit.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM entries ORDER BY date DESC, start DESC")
        return [WorkEntry(*row) for row in cursor.fetchall()]

    def insert(self, entry: WorkEntry):
        """
        Fügt einen neuen Arbeitseintrag in die Datenbank ein.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry.date, entry.start, entry.end, entry.pause,
              entry.minutes, entry.reason, entry.target_minutes, entry.entry_type))
        self.conn.commit()
        entry.id = cursor.lastrowid

    def insert_many(self, entries):
        """Fügt mehrere Arbeitseinträge in EINER Transaktion ein (alles-oder-nichts).

        Bei einem Fehler wird die gesamte Transaktion zurückgerollt, sodass keine
        teilweise importierten Einträge zurückbleiben.
        """
        cursor = self.conn.cursor()
        try:
            for entry in entries:
                cursor.execute("""
                    INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (entry.date, entry.start, entry.end, entry.pause,
                      entry.minutes, entry.reason, entry.target_minutes, entry.entry_type))
                entry.id = cursor.lastrowid
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def update(self, entry: WorkEntry):
        """
        Aktualisiert einen bestehenden Arbeitseintrag in der Datenbank.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE entries SET date=?, start=?, end=?, pause=?, minutes=?, reason=?,
                               target_minutes=?, type=? WHERE id=?
        """, (entry.date, entry.start, entry.end, entry.pause, entry.minutes,
              entry.reason, entry.target_minutes, entry.entry_type, entry.id))
        self.conn.commit()

    def delete(self, entry_id: int):
        """
        Löscht einen Arbeitseintrag anhand seiner ID.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        self.conn.commit()

    def get_last_entry_before(self, date_str: str):
        """
        Findet den zeitlich letzten Eintrag vor dem angegebenen Datum, der eine Endzeit hat.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM entries WHERE date < ? AND end != ''
            ORDER BY date DESC, end DESC LIMIT 1
        """, (date_str,))
        row = cursor.fetchone()
        return WorkEntry(*row) if row else None

    # --- Bereitschaft ---

    def load_all_bereitschaft(self):
        """
        Lädt alle Bereitschafts-Einträge aus der Datenbank, sortiert nach Datum (absteigend).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, date, start, end, note, end_date FROM bereitschaft_entries "
            "ORDER BY date DESC, start DESC"
        )
        return [
            BereitschaftEntry(
                id=row[0],
                date=row[1],
                start=row[2] or "",
                end=row[3] or "",
                note=row[4] or "",
                end_date=row[5] or "",
            )
            for row in cursor.fetchall()
        ]

    def insert_bereitschaft(self, entry: BereitschaftEntry):
        """
        Fügt einen neuen Bereitschafts-Eintrag in die Datenbank ein.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO bereitschaft_entries (date, start, end, note, end_date)
            VALUES (?, ?, ?, ?, ?)
        """, (entry.date, entry.start, entry.end, entry.note, entry.end_date))
        self.conn.commit()
        entry.id = cursor.lastrowid

    def update_bereitschaft(self, entry: BereitschaftEntry):
        """
        Aktualisiert einen bestehenden Bereitschafts-Eintrag.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE bereitschaft_entries
               SET date=?, start=?, end=?, note=?, end_date=?
             WHERE id=?
        """, (entry.date, entry.start, entry.end, entry.note, entry.end_date, entry.id))
        self.conn.commit()

    def delete_bereitschaft(self, entry_id: int):
        """
        Löscht einen Bereitschafts-Eintrag anhand seiner ID.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM bereitschaft_entries WHERE id=?", (entry_id,))
        self.conn.commit()

    # --- Device-Login (geteilte erste Login-Zeit pro Tag) ---

    def get_device_login(self, date_str: str):
        """Gibt die erste gespeicherte Login-Zeit für ein Datum zurück oder None."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT start_time FROM device_login WHERE date = ?", (date_str,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def set_device_login(self, date_str: str, start_time: str):
        """Speichert die erste Login-Zeit für ein Datum.

        Ist noch kein Eintrag für den Tag vorhanden, wird einer angelegt.
        Existiert bereits einer mit leerer start_time (z.B. durch ein
        vorheriges set_device_logout kurz nach Mitternacht), wird die
        start_time nachträglich gesetzt. Eine bereits gesetzte start_time
        bleibt unverändert (frühester Login des Tages gewinnt).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO device_login (date, start_time) VALUES (?, ?) "
            "ON CONFLICT(date) DO UPDATE SET start_time = excluded.start_time "
            "WHERE device_login.start_time = ''",
            (date_str, start_time),
        )
        self.conn.commit()

    def set_device_logout(self, date_str: str, end_time: str):
        """Speichert/aktualisiert die Logout-Zeit für ein Datum.

        Existiert noch kein Login-Eintrag für den Tag, wird einer angelegt
        (start_time bleibt leer – z.B. wenn die App erst nach dem Login
        gestartet wurde). Andernfalls wird nur end_time aktualisiert.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO device_login (date, start_time, end_time) "
            "VALUES (?, '', ?) "
            "ON CONFLICT(date) DO UPDATE SET end_time = excluded.end_time",
            (date_str, end_time),
        )
        self.conn.commit()

    def load_all_device_logins(self):
        """Lädt alle gespeicherten Login-/Logout-Zeiten, sortiert nach Datum
        (absteigend). Gibt eine Liste von Dicts mit 'date', 'start', 'end' zurück."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT date, start_time, end_time FROM device_login "
            "ORDER BY date DESC"
        )
        return [
            {"date": row[0], "start": row[1] or "", "end": row[2] or ""}
            for row in cursor.fetchall()
        ]

    # --- Abgleich mit der Server-Version (abgleich.py) ---

    def tage_lokal(self):
        """{datum: {"inhalt", "hash", "geaendert"}}: Tage mit Inhalt oder bekannter Änderung."""
        inhalte = kern.tage_gruppieren(self.load_all(), self.load_all_bereitschaft())
        zeiten = dict(self.conn.execute("SELECT date, zeit FROM tag_geaendert"))
        leer = kern.tag_inhalt()
        return {d: {"inhalt": inhalte.get(d, leer), "hash": kern.tag_hash(inhalte.get(d, leer)),
                    "geaendert": zeiten.get(d, "")}
                for d in set(inhalte) | set(zeiten)}

    def tag_hash(self, datum):
        """Aktueller Fingerabdruck eines Tages (für die Prüfung kurz vor dem Übernehmen)."""
        e = [WorkEntry(*z) for z in
             self.conn.execute("SELECT * FROM entries WHERE date = ?", (datum,))]
        b = [BereitschaftEntry(*z) for z in self.conn.execute(
            "SELECT id, date, start, end, note, end_date FROM bereitschaft_entries "
            "WHERE date = ?", (datum,))]
        return kern.tag_hash(kern.tag_inhalt(e, b))

    def abgleich_stand(self):
        """{datum: hash} beim letzten Abgleich."""
        return dict(self.conn.execute("SELECT date, hash FROM abgleich_stand"))

    def abgleich_stand_setzen(self, staende):
        """{datum: hash}; ein leerer Hash (Tag leer auf beiden Seiten) entfernt den Eintrag."""
        with self.conn:
            for datum, h in staende.items():
                if h:
                    self.conn.execute("INSERT OR REPLACE INTO abgleich_stand VALUES (?, ?)",
                                      (datum, h))
                else:
                    self.conn.execute("DELETE FROM abgleich_stand WHERE date = ?", (datum,))
                    self.conn.execute("DELETE FROM tag_geaendert WHERE date = ? AND NOT EXISTS "
                                      "(SELECT 1 FROM entries WHERE date = ?)", (datum, datum))

    def tag_ersetzen(self, datum, inhalt, geaendert):
        """Ersetzt alle Einträge/Bereitschaften eines Tages durch `inhalt` (vom Server, geprüft).

        Ohne neu zu rechnen, in einer Transaktion. Der Tag gilt danach als zum Zeitpunkt
        `geaendert` geändert."""
        with self.conn:
            self.conn.execute("DELETE FROM entries WHERE date = ?", (datum,))
            self.conn.execute("DELETE FROM bereitschaft_entries WHERE date = ?", (datum,))
            self.conn.executemany(
                "INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes, "
                "type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(datum, e["start"], e["end"], e["pause"], e["minutes"], e["reason"],
                  e["target_minutes"], e["type"]) for e in inhalt["eintraege"]])
            self.conn.executemany(
                "INSERT INTO bereitschaft_entries (date, start, end, note, end_date) "
                "VALUES (?, ?, ?, ?, ?)",
                [(datum, b["start"], b["end"], b["note"], b["end_date"])
                 for b in inhalt["bereitschaft"]])
            self.conn.execute("INSERT OR REPLACE INTO tag_geaendert VALUES (?, ?)",
                              (datum, geaendert or ""))

    def abgleich_neu_beginnen(self):
        """Nach dem Wiederherstellen eines Backups: Der hiesige Stand soll gewinnen.

        Gemeinsamen Stand vergessen und jeden Tag mit Inhalt als gerade geändert markieren
        (gelöschte Tage auch)."""
        with self.conn:
            self.conn.execute("DELETE FROM abgleich_stand")
            self.conn.execute(f"UPDATE tag_geaendert SET zeit = {_JETZT_SQL}")
            self.conn.execute(
                f"INSERT OR IGNORE INTO tag_geaendert SELECT DISTINCT date, {_JETZT_SQL} "
                f"FROM entries UNION SELECT DISTINCT date, {_JETZT_SQL} FROM bereitschaft_entries")

    # --- Backup / Wiederherstellung ---

    def backup_to(self, dest_path):
        """Schreibt eine konsistente Kopie der Datenbank nach dest_path
        (SQLite-Backup-API – auch bei offener Verbindung sicher)."""
        dest = sqlite3.connect(dest_path)
        try:
            with dest:
                self.conn.backup(dest)
        finally:
            dest.close()

    def create_backup(self, backup_dir):
        """Legt ein zeitgestempeltes Backup in backup_dir an und behält nur die
        letzten BACKUP_KEEP Stück. Gibt den Pfad des Backups zurück."""
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(backup_dir, f"ueberstunden-{timestamp}.db")
        self.backup_to(dest)
        self._prune_backups(backup_dir)
        return dest

    @staticmethod
    def _prune_backups(backup_dir, keep=BACKUP_KEEP):
        """Behält nur die `keep` neuesten Backup-Dateien im Ordner."""
        files = sorted(glob.glob(os.path.join(backup_dir, "ueberstunden-*.db")))
        for old in (files[:-keep] if keep > 0 else files):
            try:
                os.remove(old)
            except OSError:
                pass

    def restore_from(self, src_path):
        """Ersetzt den gesamten DB-Inhalt durch das Backup `src_path` und bringt
        das Schema anschließend auf den aktuellen Stand (Backup kann älter sein)."""
        src = sqlite3.connect(src_path)
        try:
            src.backup(self.conn)
        finally:
            src.close()
        self.conn.commit()
        self.create_table()

    def close(self):
        """
        Schließt die Datenbankverbindung.
        """
        self.conn.close()


_JETZT_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _trigger(tabelle, spalten):
    """Trigger, die bei jeder echten Änderung an `tabelle` den Tag in tag_geaendert vermerken
    (gleiche Regel wie in der Server-Version, web/speicher.py)."""
    markieren = ("INSERT OR REPLACE INTO tag_geaendert (date, zeit) "
                 f"VALUES ({{z}}.date, {_JETZT_SQL});")
    anders = " OR ".join(f"OLD.{sp.strip()} IS NOT NEW.{sp.strip()}"
                         for sp in ("date, " + spalten).split(","))
    return f"""
        CREATE TRIGGER IF NOT EXISTS {tabelle}_neu AFTER INSERT ON {tabelle}
        BEGIN {markieren.format(z="NEW")} END;
        CREATE TRIGGER IF NOT EXISTS {tabelle}_weg AFTER DELETE ON {tabelle}
        BEGIN {markieren.format(z="OLD")} END;
        CREATE TRIGGER IF NOT EXISTS {tabelle}_anders AFTER UPDATE ON {tabelle} WHEN {anders}
        BEGIN {markieren.format(z="OLD")} {markieren.format(z="NEW")} END;
    """
