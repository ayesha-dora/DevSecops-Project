"""
Sample Flask web application with security hardening
Used by the AI DevSecOps pipeline for testing and scanning

Features:
- API-key authentication on state-changing endpoints
- Input validation (username, email, search query)
- Rate limiting (10 requests/minute per client IP)
- Structured request logging
- Parameterized SQL queries (no SQL injection)
- Secure error handling
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
import os
import logging
import re
import time
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram
from collections import defaultdict

DB_PATH = os.environ.get('APP_DB', '/tmp/users.db')
API_KEY = os.environ.get('APP_API_KEY', 'demo-key-change-in-production')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Prometheus metrics. Previously /metrics only exposed the process/platform defaults that
# prometheus_client registers automatically — no request-level metric existed at all, so
# monitoring/prometheus.yml scraped this endpoint successfully but Grafana's "HTTP Requests Rate"
# panel (which queries rate(http_requests_total[1m])) had nothing to render and was always empty.
# "handler" is the label name because the dashboard's legendFormat is already "{{handler}}".
REQUEST_COUNT = Counter(
    'http_requests_total', 'Total HTTP requests received', ['method', 'handler', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 'HTTP request latency in seconds', ['method', 'handler']
)

# Simple in-process rate limiter (limitation: single-process only)
class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_id):
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]

        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True
        return False

rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

def get_client_id():
    """Get client identifier for rate limiting"""
    return request.remote_addr or 'unknown'

def check_rate_limit(client_id):
    """Check if client is within rate limits"""
    if not rate_limiter.is_allowed(client_id):
        # Tagged "SECURITY" to match the Loki query in monitoring/grafana-dashboard.json's
        # "Application Security Logs" panel ({job="devsecops-app"} |= "SECURITY") — previously
        # nothing the app logged contained that string, so the panel was wired up but always empty.
        logger.warning(f"SECURITY | event=rate_limit_exceeded | client={client_id}")
        return False
    return True

def validate_username(username):
    """Validate username: 1-50 chars, alphanumeric + underscore"""
    if not username or len(username) < 1 or len(username) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_email(email):
    """Validate email: basic format check, max 100 chars"""
    if not email or len(email) < 5 or len(email) > 100:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def validate_search_query(query):
    """Validate search query: 1-100 chars, alphanumeric + spaces"""
    if not query or len(query) < 1 or len(query) > 100:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_ ]+$', query))

def check_api_key():
    """Verify API key on write operations"""
    key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if key != API_KEY:
        logger.warning(f"SECURITY | event=api_key_invalid | path={request.path}")
        return False
    return True

def log_request(method, path, status, latency_ms):
    """Log structured request information and record it as a Prometheus metric. Every route
    already calls this once at the end, so it's the one place that can feed /metrics without
    touching each route individually."""
    logger.info(f"REQUEST | method={method} | path={path} | status={status} | latency_ms={latency_ms:.2f}")
    REQUEST_COUNT.labels(method=method, handler=path, status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, handler=path).observe(latency_ms / 1000.0)

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
    start = time.time()
    result = jsonify({
        "message": "AI DevSecOps Pipeline - Sample App",
        "version": "1.0.0",
        "status": "running"
    })
    latency = (time.time() - start) * 1000
    log_request('GET', '/', 200, latency)
    return result


@app.route('/health')
def health():
    start = time.time()
    result = jsonify({"status": "healthy"}), 200
    latency = (time.time() - start) * 1000
    log_request('GET', '/health', 200, latency)
    return result


@app.route('/users', methods=['GET'])
def list_users():
    start = time.time()
    try:
        conn = get_db_connection()
        cur = conn.execute('SELECT id, username, email FROM users')
        users = [dict(row) for row in cur.fetchall()]
        conn.close()
        latency = (time.time() - start) * 1000
        log_request('GET', '/users', 200, latency)
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        latency = (time.time() - start) * 1000
        log_request('GET', '/users', 500, latency)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/users', methods=['POST'])
def create_user():
    start = time.time()
    client_id = get_client_id()

    # Check rate limit
    if not check_rate_limit(client_id):
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 429, latency)
        return jsonify({"error": "Rate limit exceeded"}), 429

    # Check API key
    if not check_api_key():
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 401, latency)
        return jsonify({"error": "API key required"}), 401

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()

    # Validate inputs
    if not validate_username(username):
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 400, latency)
        return jsonify({"error": "Invalid username: 1-50 chars, alphanumeric + underscore"}), 400

    if not validate_email(email):
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 400, latency)
        return jsonify({"error": "Invalid email format"}), 400

    try:
        conn = get_db_connection()
        cur = conn.execute('INSERT INTO users (username, email) VALUES (?, ?)', (username, email))
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 201, latency)
        return jsonify({"id": user_id, "username": username, "email": email}), 201
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        latency = (time.time() - start) * 1000
        log_request('POST', '/users', 500, latency)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/search', methods=['GET'])
def search():
    """Search users by username (parameterized LIKE query)"""
    start = time.time()
    client_id = get_client_id()

    # Check rate limit
    if not check_rate_limit(client_id):
        latency = (time.time() - start) * 1000
        log_request('GET', '/search', 429, latency)
        return jsonify({"error": "Rate limit exceeded"}), 429

    query = request.args.get('q', '').strip()

    # Validate search query
    if not validate_search_query(query):
        latency = (time.time() - start) * 1000
        log_request('GET', '/search', 400, latency)
        return jsonify({"error": "Invalid search: 1-100 chars, alphanumeric + spaces"}), 400

    try:
        conn = get_db_connection()
        # Parameterized LIKE query - safe from SQL injection
        cur = conn.execute('SELECT id, username, email FROM users WHERE username LIKE ?', (f'%{query}%',))
        results = [dict(row) for row in cur.fetchall()]
        conn.close()
        latency = (time.time() - start) * 1000
        log_request('GET', '/search', 200, latency)
        return jsonify({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        latency = (time.time() - start) * 1000
        log_request('GET', '/search', 500, latency)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/dashboard')
def dashboard():
    """Human-facing landing page: live health badge, an interactive search/list/add-user demo
    against the real API below, and links out to the rest of the pipeline's tooling (Jenkins,
    SonarQube, Grafana, MLflow) on this same host. Purely presentational — every action it takes
    goes through the existing, already-tested API routes; it adds no new backend behavior.
    Share this URL, not the bare '/', when demoing the deployment."""
    start = time.time()
    result = render_template('dashboard.html')
    latency = (time.time() - start) * 1000
    log_request('GET', '/dashboard', 200, latency)
    return result


@app.route('/metrics')
def metrics():
    # Expose prometheus metrics (if any). For now return a healthy default metric.
    output = generate_latest()
    return (output, 200, {'Content-Type': CONTENT_TYPE_LATEST})


if __name__ == '__main__':
    # Run on port 5000 to match monitoring and k8s manifests
    app.run(host='0.0.0.0', port=5000, debug=False)
