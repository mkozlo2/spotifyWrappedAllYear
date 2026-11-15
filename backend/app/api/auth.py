"""Local single-account OAuth. Only a signed, HttpOnly session reaches the browser."""
import secrets
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.api.schemas import Status, Message
from app.config.settings import get_settings, BACKEND_DIR
from app.spotify.auth import create_oauth_manager, generate_state, get_authorization_url, exchange_authorization_code
from app.spotify.client import get_spotify_client
from app.repositories.spotify_repository import bind_account

router = APIRouter()


def require_session(request: Request):
    if not request.session.get('session_id') or request.session['session_id'] != request.app.state.session_id:
        raise HTTPException(401, 'Connect your Spotify account first.')


@router.get('/api/auth/status', response_model=Status)
def status(request: Request):
    settings = get_settings()
    configured = bool(settings.spotify_client_id and settings.spotify_client_secret)
    authenticated = False
    if configured and request.session.get('session_id') == request.app.state.session_id and request.app.state.session_id:
        oauth = create_oauth_manager()
        authenticated = bool(oauth.validate_token(oauth.cache_handler.get_cached_token()))
    return {'authenticated': authenticated, 'configured': configured}


@router.get('/auth/login')
def login(request: Request):
    state = generate_state()
    url = get_authorization_url(state)
    request.session.clear()
    request.session['oauth_state'] = state
    import time
    request.session['oauth_started'] = time.time()
    return RedirectResponse(url, status_code=302)


@router.get('/auth/callback')
def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    import time
    saved = request.session.pop('oauth_state', None)
    started = request.session.pop('oauth_started', 0)
    if not saved or not state or not secrets.compare_digest(saved, state) or time.time() - started > 600:
        raise HTTPException(400, 'Invalid or expired OAuth state. Please connect again.')
    if error or not code:
        raise HTTPException(400, 'Spotify authorization was declined or incomplete.')
    try:
        exchange_authorization_code(code)
        profile = get_spotify_client().current_user()
        bind_account(profile['id'])
    except ValueError as exc:
        (BACKEND_DIR / '.cache').unlink(missing_ok=True)
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, 'Could not connect to Spotify. Check credentials, permissions and redirect URI.') from exc
    request.session.clear()
    request.app.state.session_id = secrets.token_urlsafe(32)
    request.session['session_id'] = request.app.state.session_id
    return RedirectResponse(get_settings().frontend_url, status_code=303)


@router.post('/api/auth/logout', response_model=Message)
def logout(request: Request):
    require_session(request)
    request.session.clear()
    request.app.state.session_id = None
    (BACKEND_DIR / '.cache').unlink(missing_ok=True)
    return {'message': 'Disconnected locally. Collected history remains in your database.'}
