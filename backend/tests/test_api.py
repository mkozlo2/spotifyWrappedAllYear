from fastapi.testclient import TestClient
from unittest.mock import Mock
import pytest
from spotipy.exceptions import SpotifyException
from app.main import app
from app.api.auth import require_session
from app.services import spotify_service as service
from app.spotify import auth

@pytest.fixture
def client():
    # Lifespan and repository both use the isolated database fixture.
    app.dependency_overrides[require_session] = lambda: None
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def test_top_routes_and_validation(client, monkeypatch, artist, track):
    monkeypatch.setattr(service, 'fetch_top_artists', lambda *args: {'time_range': 'medium_term', 'total': 1, 'items': [artist]})
    monkeypatch.setattr(service, 'fetch_top_tracks', lambda *args: {'time_range': 'medium_term', 'total': 1, 'items': [track]})
    assert client.get('/api/top-artists').json()['items'][0]['id'] == 'a'
    assert client.get('/api/top-tracks').json()['items'][0]['id'] == 't'
    assert client.get('/api/top-tracks?limit=51').status_code == 422
    assert client.get('/api/top-tracks?time_range=all').status_code == 422


def test_snapshot_api(client, monkeypatch, track):
    monkeypatch.setattr(service, 'fetch_top', lambda *args: {'time_range': 'medium_term', 'items': [track]})
    assert client.post('/api/snapshots/tracks').status_code == 403
    response = client.post('/api/snapshots/tracks', headers={'Origin': 'http://testserver'})
    assert response.status_code == 201
    assert len(client.get('/api/snapshots/tracks').json()) == 1
    assert client.get('/api/snapshots/compare?before_id=100&after_id=101').status_code == 404
    assert client.get('/api/analytics/overview').json()['ranked_tracks'] == 1


def test_spotify_errors_are_sanitized(client, monkeypatch):
    def fail(*args):
        raise SpotifyException(429, -1, 'secret-token', headers={'Retry-After': '15'})
    monkeypatch.setattr(service, 'fetch_top_tracks', fail)
    response = client.get('/api/top-tracks')
    assert response.status_code == 429
    assert response.headers['retry-after'] == '15'
    assert 'secret-token' not in response.text


def test_unauthenticated():
    with TestClient(app) as client:
        assert client.get('/api/history').status_code == 401
        assert client.get('/api/auth/status').json()['authenticated'] is False
        assert client.get('/auth/callback?code=x&state=bad').status_code == 400


def test_recent_cursor_pagination(monkeypatch):
    spotify = Mock()
    spotify.current_user_recently_played.side_effect = [
        {'items': [], 'cursors': {'before': '12'}, 'next': 'url'}]
    monkeypatch.setattr(service, 'get_spotify_client', lambda: spotify)
    assert service.fetch_recently_played()['total'] == 0
    assert spotify.current_user_recently_played.call_count == 1


def test_recent_repeated_cursor_and_cap(monkeypatch):
    spotify = Mock()
    page = {'items': [{'track': {'id': 't', 'name': 'T'}, 'played_at': '2026-11-15T01:00:00Z'}],
            'cursors': {'before': '12'}, 'next': 'url'}
    spotify.current_user_recently_played.return_value = page
    monkeypatch.setattr(service, 'get_spotify_client', lambda: spotify)
    assert len(service.fetch_recently_played()['items']) == 2
    assert service.fetch_recently_played(max_pages=1)['page_limit_reached'] is True
