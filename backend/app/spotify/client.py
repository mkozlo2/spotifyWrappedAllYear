
from spotipy import Spotify

from app.spotify.auth import create_oauth_manager


def get_spotify_client():

    oauth = create_oauth_manager()

    token_info = oauth.validate_token(oauth.cache_handler.get_cached_token())

    if not token_info:
        raise RuntimeError("Spotify account is not connected.")

    return Spotify(
        auth_manager=oauth,
        requests_timeout=15,
        retries=0,
        status_retries=0,
        backoff_factor=0
    )
