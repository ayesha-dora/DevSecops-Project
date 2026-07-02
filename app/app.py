"""
Sample Flask Web Application
Used by DevSecOps pipeline for testing and scanning
"""

from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)

# ─── Database Setup ───────────────────────────────────────
def get_db():
    conn = sqlite3.connect('users.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY, username TEXT, email TEXT)''')
    return conn

# ─── Routes ───────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({
        "message": "AI DevSecOps Pipeline - Sample App",
        "version": "1.0.0",
        "status": "running"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/users', methods=['GET'])
def get_users():
    db = get_db()
    users = db.execute('SELECT id, username, email FROM users').fetchall()
    db.close()
    return jsonify([{"id": u[0], "username": u[1], "email": u[2]} for u in users])

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    username = data.get('username', '')
    email = data.get('email', '')

    if not username or not email:
        return jsonify({"error": "Username and email required"}), 400

    db = get_db()
    db.execute('INSERT INTO users (username, email) VALUES (?, ?)', (username, email))
    db.commit()
    db.close()
    return jsonify({"message": "User created", "username": username}), 201

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    return jsonify({"query": query, "results": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
