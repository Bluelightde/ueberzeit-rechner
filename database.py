
"""
Verwaltung der Datenbankverbindung und -operationen.
"""
import sqlite3
from models import WorkEntry, BereitschaftEntry

class DBManager:
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
        """
        Erstellt die 'entries'- und 'bereitschaft_entries'-Tabellen und führt
        notwendige Migrationen durch.
        """
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
                target_minutes INTEGER DEFAULT -1
            )
        """)
        # Migration: Check if target_minutes exists
        cursor.execute("PRAGMA table_info(entries)")
        columns = [row[1] for row in cursor.fetchall()]
        if "target_minutes" not in columns:
            cursor.execute("ALTER TABLE entries ADD COLUMN target_minutes INTEGER DEFAULT -1")

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
        # Migration: end_date für ältere Datenbanken nachziehen
        cursor.execute("PRAGMA table_info(bereitschaft_entries)")
        ber_columns = [row[1] for row in cursor.fetchall()]
        if "end_date" not in ber_columns:
            cursor.execute("ALTER TABLE bereitschaft_entries ADD COLUMN end_date TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_login (
                date TEXT PRIMARY KEY,
                start_time TEXT NOT NULL
            )
        """)
        self.conn.commit()

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
            INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entry.date, entry.start, entry.end, entry.pause,
              entry.minutes, entry.reason, entry.target_minutes))
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
                    INSERT INTO entries (date, start, end, pause, minutes, reason, target_minutes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (entry.date, entry.start, entry.end, entry.pause,
                      entry.minutes, entry.reason, entry.target_minutes))
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
                               target_minutes=? WHERE id=?
        """, (entry.date, entry.start, entry.end, entry.pause, entry.minutes,
              entry.reason, entry.target_minutes, entry.id))
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
        """Speichert die erste Login-Zeit für ein Datum. Bestehende Einträge bleiben unverändert."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO device_login (date, start_time) VALUES (?, ?)",
            (date_str, start_time),
        )
        self.conn.commit()

    def close(self):
        """
        Schließt die Datenbankverbindung.
        """
        self.conn.close()
