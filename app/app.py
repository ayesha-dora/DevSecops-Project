"""
Sample Flask web application
Used by the AI DevSecOps pipeline for testing and scanning
"""

from flask import Flask, request, jsonify
import sqlite3
import os
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

DB_PATH = os.environ.get('APP_DB', '/tmp/users.db')

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure table exists
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL
        )
        '''
    )
    conn.commit()
    return conn


@app.route('/')
def index():
    return jsonify({
        "message": "AI DevSecOps Pipeline - Sample App",
        "version": "1.0.0",
        "status": "running"
    })


@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200


@app.route('/users', methods=['GET'])
def list_users():
    conn = get_db_connection()
    cur = conn.execute('SELECT id, username, email FROM users')
    users = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(users)


@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    if not username or not email:
        return jsonify({"error": "username and email are required"}), 400

    conn = get_db_connection()
    cur = conn.execute('INSERT INTO users (username, email) VALUES (?, ?)', (username, email))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return jsonify({"id": user_id, "username": username, "email": email}), 201


@app.route('/metrics')
def metrics():
    # Expose prometheus metrics (if any). For now return a healthy default metric.
    output = generate_latest()
    return (output, 200, {'Content-Type': CONTENT_TYPE_LATEST})


if __name__ == '__main__':
    # Run on port 5000 to match monitoring and k8s manifests
    app.run(host='0.0.0.0', port=5000, debug=False)
