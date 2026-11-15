from unittest.mock import Mock
from fastapi.testclient import TestClient
from app.main import app
from app.api import auth as auth_routes
from app.spotify import client as spotify_client
from app.services import spotify_service as service
from app.repositories import spotify_repository as repo
import pytest


def test_oauth_state_success_and_logout(monkeypatch):
    monkeypatch.setattr(auth_routes, 'get_authorization_url', lambda state: 'https://accounts.spotify.com/authorize?state=' + state)
    exchange = Mock()
    monkeypatch.setattr(auth_routes, 'exchange_authorization_code', exchange)
    spotify = Mock()
    spotify.current_user.return_value = {'id': 'owner'}
    monkeypatch.setattr(auth_routes, 'get_spotify_client', lambda: spotify)
    # Never remove the real local token cache in tests.
    from pathlib import Path
    monkeypatch.setattr(Path, 'unlink', lambda *args, **kwargs: None)
    with TestClient(app) as client:
        response = client.get('/auth/login', follow_redirects=False)
        state = response.headers['location'].split('state=')[1]
        assert 'httponly' in response.headers['set-cookie'].lower()
        assert client.get('/auth/callback?code=secret&state='+state, follow_redirects=False).status_code == 303
        exchange.assert_called_once_with('secret')
        assert client.get('/api/history').status_code == 200
        assert client.get('/auth/callback?code=secret&state='+state).status_code == 400
        assert client.post('/api/auth/logout', headers={'Origin':'http://testserver'}).status_code == 200
        assert client.get('/api/history').status_code == 401


def test_sync_idempotency(client, monkeypatch, artist, track):
    monkeypatch.setattr(service, 'fetch_profile', lambda: {'id':'owner'})
    monkeypatch.setattr(service, 'fetch_top', lambda kind, *args: {'time_range':'medium_term','items':[artist if kind=='artists' else track]})
    monkeypatch.setattr(service, 'fetch_recently_played', lambda: {'items':[{'played_at':'2026-11-15T10:00:00Z','track':track}], 'total':1,'page_limit_reached':False})
    headers={'Origin':'http://testserver'}
    first=client.post('/api/sync',headers=headers)
    assert first.status_code == 200
    assert first.json()['saved_events'] == 1
    second=client.post('/api/sync',headers=headers)
    assert second.json()['saved_events'] == 0
    assert all(s['reused'] for s in second.json()['snapshots'])


def test_client_validates_and_refreshes_cache(monkeypatch):
    oauth=Mock()
    oauth.cache_handler.get_cached_token.return_value={'refresh_token':'refresh','expires_at':0}
    oauth.validate_token.return_value={'access_token':'refreshed'}
    monkeypatch.setattr(spotify_client,'create_oauth_manager',lambda:oauth)
    factory=Mock()
    monkeypatch.setattr(spotify_client,'Spotify',factory)
    spotify_client.get_spotify_client()
    oauth.validate_token.assert_called_once_with(oauth.cache_handler.get_cached_token.return_value)
    assert factory.call_args.kwargs['auth_manager'] is oauth
    oauth.validate_token.return_value=None
    with pytest.raises(RuntimeError):
        spotify_client.get_spotify_client()
