"""
Unit Tests for Sample Flask Application
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, API_KEY

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home(client):
    """Test home endpoint returns 200"""
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'running'

def test_health(client):
    """Test health endpoint returns healthy"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'

def test_get_users(client):
    """Test get users endpoint"""
    response = client.get('/users')
    assert response.status_code == 200

def test_create_user(client):
    """Test create user endpoint (requires the API key added alongside auth hardening)"""
    response = client.post('/users', json={
        'username': 'testuser',
        'email': 'test@example.com'
    }, headers={'X-API-Key': API_KEY})
    assert response.status_code == 201

def test_create_user_missing_fields(client):
    """Test create user with missing fields returns 400 (API key present, so auth isn't
    what's being tested here)"""
    response = client.post('/users', json={}, headers={'X-API-Key': API_KEY})
    assert response.status_code == 400

def test_create_user_no_api_key(client):
    """Test create user without an API key is rejected"""
    response = client.post('/users', json={
        'username': 'testuser2',
        'email': 'test2@example.com'
    })
    assert response.status_code == 401

def test_dashboard(client):
    """Test the human-facing dashboard page renders"""
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'AI-Augmented DevSecOps Pipeline' in response.data

def test_metrics_records_requests(client):
    """Test /metrics actually exposes http_requests_total after a request, not just the
    process/platform defaults prometheus_client registers on its own (this is what feeds
    Grafana's 'HTTP Requests Rate' panel — see app.py's REQUEST_COUNT for the fix this covers)"""
    client.get('/health')
    response = client.get('/metrics')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'http_requests_total' in body
    assert 'handler="/health"' in body

def test_security_events_are_tagged_for_loki(client, caplog):
    """Test that a rejected write is both a 401 AND logged with the 'SECURITY' marker the Grafana
    dashboard's Loki panel filters on ({job="devsecops-app"} |= "SECURITY") — without this tag the
    panel is wired up correctly end-to-end but has nothing matching its query to display."""
    with caplog.at_level('WARNING'):
        response = client.post('/users', json={'username': 'x', 'email': 'x@example.com'})
    assert response.status_code == 401
    assert any('SECURITY' in record.message for record in caplog.records)

def test_search(client):
    """Test search endpoint"""
    response = client.get('/search?q=test')
    assert response.status_code == 200
