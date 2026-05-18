"""Generiert eine Demo-Datenbank mit realistischen Beispieldaten."""
import sqlite3, random, os
from datetime import date, timedelta

random.seed(42)

DB_PATH = "demo_daten.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.execute(
    "CREATE TABLE entries ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "date TEXT NOT NULL,"
    "start TEXT,"
    "end TEXT,"
    "pause INTEGER,"
    "minutes INTEGER,"
    "reason TEXT,"
    "target_minutes INTEGER DEFAULT -1)"
)

TARGET = 480  # 8h Soll

REASONS = [
    "", "", "", "",
    "Projektmeeting", "Kundengespräch", "Code Review",
    "Deployment", "Schulung", "Teammeeting", "Überstunden abgebaut",
]

FEIERTAGE = {
    "2026-04-03", "2026-04-06",  # Karfreitag / Ostermontag
    "2026-05-01",                # Tag der Arbeit
    "2026-05-14",                # Christi Himmelfahrt
}

start_date = date(2026, 2, 2)
end_date   = date(2026, 5, 15)

entries = []
d = start_date
while d <= end_date:
    if d.weekday() >= 5 or d.strftime("%Y-%m-%d") in FEIERTAGE:
        d += timedelta(days=1)
        continue

    ds = d.strftime("%Y-%m-%d")

    # Gelegentlich Urlaub oder Krank
    if random.random() < 0.04:
        reason = random.choice(["Urlaub", "Krank"])
        entries.append((ds, "", "", 0, -TARGET, reason, -1))
        d += timedelta(days=1)
        continue

    start_h = random.randint(7, 9)
    start_m = random.choice([0, 0, 15, 30, 45])
    variation = random.randint(-60, 120)
    work_mins = TARGET + variation

    if work_mins >= 510:
        pause_m = 45
    elif work_mins >= 330:
        pause_m = 30
    else:
        pause_m = 0

    total_mins = work_mins + pause_m
    end_total = start_h * 60 + start_m + total_mins
    end_h, end_mm = divmod(end_total, 60)
    overtime = work_mins - TARGET
    reason = random.choice(REASONS)

    entries.append((ds,
        f"{start_h:02d}:{start_m:02d}",
        f"{end_h:02d}:{end_mm:02d}",
        pause_m, overtime, reason, -1))

    d += timedelta(days=1)

conn.executemany(
    "INSERT INTO entries (date,start,end,pause,minutes,reason,target_minutes)"
    " VALUES (?,?,?,?,?,?,?)",
    entries
)
conn.commit()
conn.close()

total = sum(e[4] for e in entries)
h, m = divmod(abs(total), 60)
sign = "+" if total >= 0 else "-"
print(f"Einträge:     {len(entries)}")
print(f"Gesamtsaldo:  {sign}{h}h {m}min")
print(f"Gespeichert:  {DB_PATH}")
