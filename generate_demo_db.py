"""Generiert eine Demo-Datenbank mit realistischen Beispieldaten."""
import os
import random
import sqlite3
from datetime import date, timedelta


def main():
    """Erstellt demo_daten.db mit realistischen Arbeitszeitdaten."""
    random.seed(42)

    db_path = "demo_daten.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
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

    target = 480  # 8h Soll

    reasons = [
        "", "", "", "",
        "Projektmeeting", "Kundengespräch", "Code Review",
        "Deployment", "Schulung", "Teammeeting", "Überstunden abgebaut",
    ]

    feiertage = {
        "2026-04-03", "2026-04-06",
        "2026-05-01",
        "2026-05-14",
    }

    entries = []
    day = date(2026, 2, 2)
    end_date = date(2026, 5, 15)

    while day <= end_date:
        if day.weekday() >= 5 or day.strftime("%Y-%m-%d") in feiertage:
            day += timedelta(days=1)
            continue

        ds = day.strftime("%Y-%m-%d")

        if random.random() < 0.04:
            reason = random.choice(["Urlaub", "Krank"])
            entries.append((ds, "", "", 0, -target, reason, -1))
            day += timedelta(days=1)
            continue

        start_h = random.randint(7, 9)
        start_m = random.choice([0, 0, 15, 30, 45])
        work_mins = target + random.randint(-60, 120)

        if work_mins >= 510:
            pause_minutes = 45
        elif work_mins >= 330:
            pause_minutes = 30
        else:
            pause_minutes = 0

        end_total = start_h * 60 + start_m + work_mins + pause_minutes
        end_h, end_mm = divmod(end_total, 60)
        overtime = work_mins - target

        entries.append((ds,
            f"{start_h:02d}:{start_m:02d}",
            f"{end_h:02d}:{end_mm:02d}",
            pause_minutes, overtime, random.choice(reasons), -1))

        day += timedelta(days=1)

    conn.executemany(
        "INSERT INTO entries (date,start,end,pause,minutes,reason,target_minutes)"
        " VALUES (?,?,?,?,?,?,?)",
        entries
    )
    conn.commit()
    conn.close()

    total = sum(e[4] for e in entries)
    hours, mins = divmod(abs(total), 60)
    sign = "+" if total >= 0 else "-"
    print(f"Einträge:     {len(entries)}")
    print(f"Gesamtsaldo:  {sign}{hours}h {mins}min")
    print(f"Gespeichert:  {db_path}")


if __name__ == "__main__":
    main()
