
"""
Verwaltung der Datenbankverbindung und -operationen.
"""
import sqlite3
from models import WorkEntry

class DBManager:
    """
    Verwaltet die SQLite-Datenbankverbindung und Operationen für Arbeitseinträge.
    """
    def __init__(self, db_path):
        """
        Initialisiert den DBManager und erstellt die Tabelle, falls sie nicht existiert.
        """
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        """
        Erstellt die 'entries'-Tabelle und führt notwendige Migrationen durch.
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

    def close(self):
        """
        Schließt die Datenbankverbindung.
        """
        self.conn.close()
