"""
seed.py — Cloud Café database seeder
Run once before the hackathon demo:  python seed.py

Creates database.db with:
  - journal_entries  (10 entries over the past 2 weeks)
  - mood_logs        (20 entries over the past 3 weeks)
  - user_stats       (demo coins + streak so closet is usable)
  - wardrobe         (one item pre-purchased for demo)

Safe to re-run — drops and recreates all tables fresh.
"""

import sqlite3
from datetime import datetime, timedelta
import random

DB = "database.db"

JOURNAL_ENTRIES = [
    ("today was actually really nice. had a slow morning with coffee and just sat by the window for a while. felt like i could breathe.", "calm"),
    ("couldn't sleep last night. my mind kept racing about everything i have to do. made a list at 2am which helped a little.", "anxious"),
    ("went for a walk after lunch and ran into my neighbour's dog. honestly the highlight of my week.", "happy"),
    ("feeling a bit off today. not sad exactly, just sort of grey. hard to explain.", "tired"),
    ("had a really good conversation with my friend today. reminded me why i value that friendship so much.", "happy"),
    ("work was overwhelming. too many things coming at me at once. need to figure out how to set better limits.", "frustrated"),
    ("woke up feeling hopeful today for no particular reason. sometimes it just hits like that.", "hopeful"),
    ("missing people i haven't seen in a while. it's a strange kind of lonely, not bad just present.", "lonely"),
    ("finished something i've been putting off for weeks. felt so good to just get it done.", "content"),
    ("rainy day. stayed in, made soup, read. sometimes that's exactly what the week needed.", "calm"),
]

MOODS = [
    ("happy",       "good morning"),
    ("calm",        "quiet afternoon"),
    ("anxious",     "before a meeting"),
    ("tired",       "end of day"),
    ("hopeful",     "fresh start"),
    ("content",     "just checking in"),
    ("frustrated",  "too much on my plate"),
    ("lonely",      ""),
    ("sad",         "missing home"),
    ("calm",        "evening walk"),
    ("happy",       "good news today"),
    ("anxious",     ""),
    ("hopeful",     "things are looking up"),
    ("tired",       "didn't sleep well"),
    ("content",     "slow sunday"),
    ("calm",        ""),
    ("happy",       "laughed a lot today"),
    ("frustrated",  "communication issues"),
    ("hopeful",     "new week"),
    ("calm",        "before bed"),
]

def seed():
    conn = sqlite3.connect(DB)
    c    = conn.cursor()

    # drop all tables and recreate fresh
    for table in ["journal_entries", "mood_logs", "lab_results", "user_stats", "wardrobe"]:
        c.execute(f"DROP TABLE IF EXISTS {table}")

    c.execute("""CREATE TABLE journal_entries (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        entry TEXT, mood TEXT,
        date  TIMESTAMP
    )""")

    c.execute("""CREATE TABLE mood_logs (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        mood TEXT, note TEXT,
        date TIMESTAMP
    )""")

    c.execute("""CREATE TABLE lab_results (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text       TEXT, ai_explanation TEXT,
        date           TIMESTAMP
    )""")

    c.execute("""CREATE TABLE user_stats (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        coins      INTEGER DEFAULT 0,
        last_login TEXT,
        streak     INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE wardrobe (
        item_slug TEXT PRIMARY KEY,
        purchased INTEGER DEFAULT 0,
        equipped  INTEGER DEFAULT 0
    )""")

    now = datetime.now()

    # seed journal entries — spread over last 14 days
    for i, (entry, mood) in enumerate(JOURNAL_ENTRIES):
        days_ago = len(JOURNAL_ENTRIES) - i
        hour     = random.randint(8, 22)
        dt       = now - timedelta(days=days_ago, hours=24-hour)
        c.execute("INSERT INTO journal_entries (entry, mood, date) VALUES (?, ?, ?)",
                  (entry, mood, dt.strftime("%Y-%m-%d %H:%M:%S")))

    # seed mood logs — spread over last 21 days
    for i, (mood, note) in enumerate(MOODS):
        days_ago = len(MOODS) - i
        hour     = random.randint(7, 23)
        dt       = now - timedelta(days=days_ago, hours=24-hour)
        c.execute("INSERT INTO mood_logs (mood, note, date) VALUES (?, ?, ?)",
                  (mood, note, dt.strftime("%Y-%m-%d %H:%M:%S")))

    # seed user stats — give judges enough coins to buy things in the demo
    # 120 coins so they can try buying items right away
    c.execute("INSERT INTO user_stats (coins, last_login, streak) VALUES (120, ?, 7)",
              (str(now.date()),))

    # pre-purchase one item so the closet doesn't look empty
    # judges can see what an owned item looks like immediately
    c.execute("INSERT INTO wardrobe (item_slug, purchased, equipped) VALUES ('hat-beret', 1, 1)")

    conn.commit()
    conn.close()

    print("database.db seeded successfully")
    print(f"  {len(JOURNAL_ENTRIES)} journal entries")
    print(f"  {len(MOODS)} mood logs")
    print("  user starts with 120 coins, 7-day streak")
    print("  hat-beret pre-purchased and equipped")
    print("\nrun:  python app.py")

if __name__ == "__main__":
    seed()