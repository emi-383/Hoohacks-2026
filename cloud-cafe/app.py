from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai                          # new SDK
import sqlite3, os
from datetime import date

load_dotenv()
app    = Flask(__name__)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # new client style

# ── Database ───────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS journal_entries (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        entry TEXT, mood TEXT,
        date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS mood_logs (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        mood TEXT, note TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lab_results (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text       TEXT, ai_explanation TEXT,
        date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_stats (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        coins      INTEGER DEFAULT 0,
        last_login TEXT,
        streak     INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS wardrobe (
        item_slug TEXT PRIMARY KEY,
        purchased INTEGER DEFAULT 0,
        equipped  INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

init_db()

# ── Helper: award a coin ───────────────────────────────────────
def award_coin(conn):
    conn.cursor().execute("UPDATE user_stats SET coins = coins + 1")

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
@app.route("/api/login-reward", methods=["POST"])
def login_reward():
    conn  = sqlite3.connect("database.db")
    c     = conn.cursor()
    today = str(date.today())
    c.execute("SELECT id, coins, last_login, streak FROM user_stats LIMIT 1")
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO user_stats (coins, last_login, streak) VALUES (1, ?, 1)", (today,))
        rewarded, coins, streak = True, 1, 1
    elif row[2] != today:
        new_coins, new_streak = row[1] + 1, row[3] + 1
        c.execute("UPDATE user_stats SET coins=?, last_login=?, streak=?", (new_coins, today, new_streak))
        rewarded, coins, streak = True, new_coins, new_streak
    else:
        rewarded, coins, streak = False, row[1], row[3]
    conn.commit()
    conn.close()
    return jsonify({"rewarded": rewarded, "coins": coins, "streak": streak})

@app.route("/api/coins", methods=["GET"])
def get_coins():
    conn = sqlite3.connect("database.db")
    c    = conn.cursor()
    c.execute("SELECT coins, streak FROM user_stats LIMIT 1")
    row  = c.fetchone()
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
    award_coin(conn)
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
    award_coin(conn)
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
    award_coin(conn)
    conn.commit()
    conn.close()

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite", # Changed from 2.0 to 1.5
            contents="Write ONE short, warm affirmation (1 sentence). No emojis."
        )
        return jsonify({"fortune": response.text.strip()})
    except Exception as e:
        print(f"Fortune Error: {e}")
        return jsonify({"fortune": "you are doing enough."})

# ── Mochi Chatbot API ──────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    history = request.json.get("history", [])

    # 1. Fetch DB Context
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT mood FROM mood_logs ORDER BY date DESC LIMIT 5")
    recent_moods = [row[0].lower() for row in c.fetchall()]
    c.execute("SELECT entry FROM journal_entries ORDER BY date DESC LIMIT 1")
    last_journal = c.fetchone()
    last_journal_text = last_journal[0][:120] if last_journal else "nothing yet"
    conn.close()

    # 2. System Prompt
    system_prompt = f"""You are Mochi, a warm cat owning Cloud Café. 
    Context: Recent moods: {', '.join(recent_moods)}. Last journal: {last_journal_text}.
    Speak gently. If the user is very sad, suggest calling 988."""

    # 3. Format History
    formatted_history = []
    for msg in history:
        role = "user" if msg.get("role") == "user" else "model"
        text_content = msg.get("content") or (msg.get("parts")[0].get("text") if msg.get("parts") else "")
        if text_content:
            formatted_history.append({"role": role, "parts": [{"text": str(text_content)}]})

    try:
        # Create chat session with Safety Settings set to 'BLOCK_NONE'
        # This prevents the AI from blocking supportive mental health talk
        chat_session = client.chats.create(
            model="gemini-2.0-flash-lite",
            config={
                "system_instruction": system_prompt,
            },
            history=formatted_history
        )
        
        response = chat_session.send_message(user_message)
        return jsonify({"reply": response.text})
    
    except Exception as e:
        # Check your VS Code terminal for this output!
        print(f"--- MOCHI ERROR: {e} ---")
        return jsonify({"reply": "purr... my whiskers are twitching. try again in a second?"}), 500

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
    c.execute("""INSERT INTO wardrobe (item_slug, purchased, equipped) VALUES (?, 1, 0)
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
    c.execute("UPDATE wardrobe SET equipped=? WHERE item_slug=?", (1 if equipped else 0, slug))
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})

@app.route("/api/wardrobe/equipped", methods=["GET"])
def get_equipped():
    conn  = sqlite3.connect("database.db")
    c     = conn.cursor()
    c.execute("SELECT item_slug FROM wardrobe WHERE equipped=1")
    items = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"equipped": items})

if __name__ == "__main__":
    app.run(debug=True)