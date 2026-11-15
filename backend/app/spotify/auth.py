import secrets
from pathlib import Path

from spotipy.oauth2 import SpotifyOAuth

from app.config.settings import get_settings

SCOPES = [
    "user-top-read",
    "user-read-recently-played",
]

def create_oauth_manager():
    settings = get_settings()
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise RuntimeError("Configure Spotify credentials in backend/.env first.")

    backend_dir = Path(__file__).resolve().parents[2]

    return SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=str(backend_dir / ".cache"),
        show_dialog=True
    )

def generate_state():
    return secrets.token_urlsafe(32)

def get_authorization_url(state: str):
    oauth = create_oauth_manager()

    return oauth.get_authorize_url(state=state)

def exchange_authorization_code(code: str):
    oauth = create_oauth_manager()

    return oauth.get_access_token(
        code,
        as_dict=True,
        check_cache=False
    )
