import re
import sqlite3
import os
from flask import Flask, render_template, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Load Environment Variables ----------
load_dotenv()

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY is missing in .env file")
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- Flask App ----------
app = Flask(__name__)

DATABASE = 'users.db'

# ---------- DB Helper ----------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            rollNo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')
        db.commit()

# Initialize DB
init_db()

# ---------- Routes ----------
@app.route('/')
def home():
    return render_template('index.html')


# ---------- Sign Up Route ----------
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    role = data.get('role', 'student')
    rollNo = data.get('rollNo')
    password = data.get('password')

    if not name or not rollNo or not password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    # Validate roll number format
    if role == 'student':
        pattern = r'^\d{2}[A-Z]{3}\d{5}$'
        if not re.match(pattern, rollNo):
            return jsonify({"success": False, "message": "Invalid Roll Number Format"}), 400

    hashed_pw = generate_password_hash(password)

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (name, role, rollNo, password) VALUES (?, ?, ?, ?)",
                       (name, role, rollNo, hashed_pw))
        db.commit()
        return jsonify({"success": True, "message": "Sign-Up Successful"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "User already exists"}), 409

# ---------- Login Route ----------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    rollNo = data.get('rollNo')
    password = data.get('password')

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name, role, password FROM users WHERE rollNo = ?", (rollNo,))
    user = cursor.fetchone()

    if user and check_password_hash(user[2], password):
        return jsonify({"success": True, "message": "Login Successful", "role": user[1], "name": user[0]})
    else:
        return jsonify({"success": False, "message": "Invalid Credentials"}), 401

# ---------- AI Doubt Helper Route ----------
@app.route('/api/ask-ai', methods=['POST'])
def ask_ai():
    try:
        data = request.json
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "Question cannot be empty"}), 400

        # Call OpenAI model
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Light, fast model
            messages=[
                {"role": "system", "content": "You are a helpful academic assistant."},
                {"role": "user", "content": question}
            ]
        )

        answer = response.choices[0].message.content
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- Run the App ----------
if __name__ == '__main__':
    app.run(debug=True)
