# =============================================================================
# FILE: app/tests/probes/test_health_.py
# DESCRIPTION: Unit test for /api/v1/health endpoint.
# =============================================================================

"""Health endpoint tests."""
import pytest


def test_v1_health_endpoint(client):
    """Test /api/v1/health returns 200 with correct data."""
    response = client.get('/api/v1/health')
    
    # Assert status code
    assert response.status_code == 200
    
    # Get JSON response
    data = response.get_json()
    
    # Assert response structure
    assert data['status'] == 'success'
    assert data['data']['database'] == 'ok'
    assert data['data']['status'] == 'ok'
    assert 'current_time' in data['data']
    
    print(f"\n✅ Health check passed!")
    print(f"   Status: {response.status_code}")
    print(f"   Database: {data['data']['database']}")
    print(f"   Timestamp: {data['data']['current_time']}")


def test_api_health_endpoint(client):
    """Test /api/health endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200


def test_api_ping_endpoint(client):
    """Test /api/ping endpoint."""
    response = client.get('/api/ping')
    assert response.status_code == 200


def test_version_endpoint(client):
    """Test /version endpoint."""
    response = client.get('/version')
    assert response.status_code == 200