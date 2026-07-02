"""
Unit Tests for Sample Flask Application
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

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
    """Test create user endpoint"""
    response = client.post('/users', json={
        'username': 'testuser',
        'email': 'test@example.com'
    })
    assert response.status_code == 201

def test_create_user_missing_fields(client):
    """Test create user with missing fields returns 400"""
    response = client.post('/users', json={})
    assert response.status_code == 400

def test_search(client):
    """Test search endpoint"""
    response = client.get('/search?q=test')
    assert response.status_code == 200
