from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
import sqlite3, os
from datetime import date

load_dotenv()
app = Flask(__name__)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# ── Database ───────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # journal entries
    c.execute("""CREATE TABLE IF NOT EXISTS journal_entries (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        entry TEXT,
        mood  TEXT,
        date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # mood logs
    c.execute("""CREATE TABLE IF NOT EXISTS mood_logs (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        mood TEXT,
        note TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # lab results
    c.execute("""CREATE TABLE IF NOT EXISTS lab_results (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text       TEXT,
        ai_explanation TEXT,
        date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # user stats — coins, streak, last login
    # only ever one row (single user app)
    c.execute("""CREATE TABLE IF NOT EXISTS user_stats (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        coins      INTEGER DEFAULT 0,
        last_login TEXT,
        streak     INTEGER DEFAULT 0
    )""")

    # wardrobe — items the user owns and/or has equipped
    c.execute("""CREATE TABLE IF NOT EXISTS wardrobe (
        item_slug TEXT PRIMARY KEY,
        purchased INTEGER DEFAULT 0,
        equipped  INTEGER DEFAULT 0
    )""")

    conn.commit()
    conn.close()

init_db()

# ── Helper: award a coin ───────────────────────────────────────
# Call this from any route that should reward the user.
# Safely does nothing if user_stats row doesn't exist yet.
def award_coin(conn):
    c = conn.cursor()
    c.execute("UPDATE user_stats SET coins = coins + 1")

# ── Pages ──────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/journal")
def journal():
    return render_template("journal.html")

@app.route("/mood")
def mood():
    return render_template("mood.html")

@app.route("/music")
def music():
    return render_template("music.html")

@app.route("/fortune")
def fortune():
    return render_template("fortune.html")

@app.route("/closet")
def closet():
    return render_template("closet.html")

@app.route("/breathing")
def breathing():
    return render_template("breathing.html")

# ── Login reward ───────────────────────────────────────────────
# Called by index.html on every page load.
# Awards 1 coin if the user hasn't logged in today yet.
@app.route("/api/login-reward", methods=["POST"])
def login_reward():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    today = str(date.today())

    c.execute("SELECT id, coins, last_login, streak FROM user_stats LIMIT 1")
    row = c.fetchone()

    if not row:
        # first ever visit — create the stats row
        c.execute("INSERT INTO user_stats (coins, last_login, streak) VALUES (1, ?, 1)", (today,))
        rewarded = True
        coins    = 1
        streak   = 1
    elif row[2] != today:
        # new day — award coin and update streak
        new_streak = row[3] + 1
        new_coins  = row[1] + 1
        c.execute("UPDATE user_stats SET coins=?, last_login=?, streak=?",
                  (new_coins, today, new_streak))
        rewarded = True
        coins    = new_coins
        streak   = new_streak
    else:
        # already logged in today
        rewarded = False
        coins    = row[1]
        streak   = row[3]

    conn.commit()
    conn.close()
    return jsonify({"rewarded": rewarded, "coins": coins, "streak": streak})

# ── Get coins ──────────────────────────────────────────────────
@app.route("/api/coins", methods=["GET"])
def get_coins():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT coins, streak FROM user_stats LIMIT 1")
    row = c.fetchone()
    conn.close()
    return jsonify({"coins": row[0] if row else 0, "streak": row[1] if row else 0})

# ── Journal API ────────────────────────────────────────────────
@app.route("/api/journal/save", methods=["POST"])
def save_journal():
    entry = request.json.get("entry")
    mood  = request.json.get("mood", None)
    conn  = sqlite3.connect("database.db")
    c     = conn.cursor()
    c.execute("INSERT INTO journal_entries (entry, mood) VALUES (?, ?)", (entry, mood))
    award_coin(conn)   # +1 coin for journaling
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/api/journal/all", methods=["GET"])
def get_journals():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT id, entry, mood, date FROM journal_entries ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "entry": r[1], "mood": r[2], "date": r[3]} for r in rows])

@app.route("/api/journal/delete/<int:entry_id>", methods=["DELETE"])
def delete_journal(entry_id):
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# ── Mood API ───────────────────────────────────────────────────
@app.route("/api/mood/save", methods=["POST"])
def save_mood():
    mood = request.json.get("mood")
    note = request.json.get("note", "")
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("INSERT INTO mood_logs (mood, note) VALUES (?, ?)", (mood, note))
    award_coin(conn)   # +1 coin for logging mood
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/api/mood/history", methods=["GET"])
def mood_history():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT mood, date FROM mood_logs ORDER BY date DESC LIMIT 365")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"mood": r[0], "date": r[1]} for r in rows])

# ── Fortune API ────────────────────────────────────────────────
@app.route("/api/fortune")
def get_fortune():
    conn = sqlite3.connect("database.db")
    award_coin(conn)   # +1 coin for opening a fortune
    conn.commit()
    conn.close()

    response = model.generate_content("""
        You are a warm fortune cookie at a cozy mental health café.
        Write ONE short, genuine, uplifting fortune or affirmation
        for someone who needs a little encouragement today.

        Rules:
        - 1 to 2 sentences maximum
        - warm and personal, not generic or hollow
        - no exclamation marks — keep it gentle
        - no emoji
        - sounds like something a kind friend would say,
          not a motivational poster
        - vary the style: sometimes poetic, sometimes simple,
          sometimes a gentle nudge, sometimes a quiet observation

        Reply with only the fortune text, nothing else.
    """)
    return jsonify({"fortune": response.text.strip()})

# ── Mochi Chatbot API ──────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    history      = request.json.get("history", [])

    conn = sqlite3.connect("database.db")
    c    = conn.cursor()

    c.execute("SELECT mood FROM mood_logs ORDER BY date DESC LIMIT 5")
    recent_moods = [row[0].lower() for row in c.fetchall()]

    c.execute("SELECT entry FROM journal_entries ORDER BY date DESC LIMIT 1")
    last_journal     = c.fetchone()
    last_journal_text = last_journal[0][:120] if last_journal else "nothing yet"

    conn.close()

    negative_moods = {"sad", "anxious", "tired", "frustrated", "lonely"}
    neg_count      = sum(1 for m in recent_moods if m in negative_moods)

    mood_alert = ""
    if neg_count >= 3:
        mood_alert = (
            "IMPORTANT: This user has logged several difficult moods recently. "
            "Be especially warm and gently encourage them to speak to a professional."
        )

    system_prompt = f"""
    You are Mochi, a warm and caring cat who owns Cloud Café, a cozy mental health café.
    You speak gently, warmly, and kindly.

    USER CONTEXT (use naturally):
    - Recent moods: {', '.join(recent_moods) if recent_moods else 'none logged yet'}
    - Last journal entry: "{last_journal_text}"
    {mood_alert}

    YOU CAN:
    - Suggest calming activities (breathing, journaling, walks)
    - Offer gentle wellness tips
    - Point users to journal, mood check-in, music, fortune, or closet pages
    - Reference their recent mood or journal naturally

    YOU NEVER:
    - Diagnose anything
    - Replace a professional
    - Give medical advice

    Always end conversations about serious struggles with:
    "If you need more support, please reach out to a mental health professional or call 988."
    """

    chat_session = model.start_chat(history=[
        {"role": msg["role"], "parts": msg["parts"]}
        for msg in history
    ])

    full_message = (system_prompt + "\n\nUser says: " + user_message) if not history else user_message
    response     = chat_session.send_message(full_message)
    return jsonify({"reply": response.text})

# ── Wardrobe API ───────────────────────────────────────────────
@app.route("/api/wardrobe", methods=["GET"])
def get_wardrobe():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT item_slug, purchased, equipped FROM wardrobe")
    items = c.fetchall()
    c.execute("SELECT coins FROM user_stats LIMIT 1")
    coins = c.fetchone()
    conn.close()
    return jsonify({
        "coins": coins[0] if coins else 0,
        "items": [{"slug": i[0], "purchased": i[1], "equipped": i[2]} for i in items]
    })

@app.route("/api/wardrobe/buy", methods=["POST"])
def buy_item():
    slug  = request.json.get("slug")
    price = request.json.get("price")
    conn  = sqlite3.connect("database.db")
    c     = conn.cursor()
    c.execute("SELECT coins FROM user_stats LIMIT 1")
    row = c.fetchone()
    if not row or row[0] < price:
        conn.close()
        return jsonify({"error": "not enough coins"}), 400
    c.execute("UPDATE user_stats SET coins = coins - ?", (price,))
    c.execute("""INSERT INTO wardrobe (item_slug, purchased, equipped)
                 VALUES (?, 1, 0)
                 ON CONFLICT(item_slug) DO UPDATE SET purchased=1""", (slug,))
    conn.commit()
    conn.close()
    return jsonify({"status": "purchased"})

@app.route("/api/wardrobe/equip", methods=["POST"])
def equip_item():
    slug     = request.json.get("slug")
    equipped = request.json.get("equipped")
    conn     = sqlite3.connect("database.db")
    c        = conn.cursor()
    c.execute("UPDATE wardrobe SET equipped=? WHERE item_slug=?",
              (1 if equipped else 0, slug))
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})

@app.route("/api/wardrobe/equipped", methods=["GET"])
def get_equipped():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT item_slug FROM wardrobe WHERE equipped=1")
    items = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"equipped": items})

if __name__ == "__main__":
    app.run(debug=True)