from contextlib import asynccontextmanager
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from spotipy.exceptions import SpotifyException, SpotifyOauthError
from requests.exceptions import RequestException
from app.config.settings import get_settings, BACKEND_DIR
from app.database.connection import Base, engine
from app.database import models
from app.api import auth, routes

settings = get_settings()

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title='Soundprint · Personal Spotify Analytics', version='1.0.0', lifespan=lifespan)
app.state.session_id = None
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret or secrets.token_urlsafe(48),
                   session_cookie='soundprint_session', same_site='lax', https_only=settings.cookie_secure, max_age=86400)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url], allow_credentials=True,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

@app.middleware('http')
async def local_security(request: Request, call_next):
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        origin = request.headers.get('origin')
        allowed = {settings.frontend_url, str(request.base_url).rstrip('/')}
        if origin not in allowed:
            return JSONResponse(status_code=403, content={'detail': 'Untrusted request origin.'})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.exception_handler(SpotifyException)
async def spotify_error(request, exc):
    code = exc.http_status if exc.http_status in (401, 403, 404, 429) else 502
    messages = {401: 'Spotify session expired. Reconnect your account.',
                403: 'Spotify denied this endpoint. Check app access and reconnect for updated permissions.',
                404: 'This Spotify item is unavailable.', 429: 'Spotify rate limit reached. Try again later.'}
    headers = {'Retry-After': str((exc.headers or {}).get('Retry-After', '30'))} if code == 429 else {}
    return JSONResponse(status_code=code, content={'detail': messages.get(code, 'Spotify is temporarily unavailable.')}, headers=headers)

@app.exception_handler(RuntimeError)
async def runtime_error(request, exc):
    return JSONResponse(status_code=401, content={'detail': str(exc)})

@app.exception_handler(SpotifyOauthError)
async def oauth_error(request, exc):
    return JSONResponse(status_code=401, content={'detail': 'Spotify authorization expired. Reconnect your account.'})

@app.exception_handler(ValueError)
async def validation_error(request, exc):
    return JSONResponse(status_code=400, content={'detail': str(exc)})

@app.exception_handler(LookupError)
async def missing(request, exc):
    return JSONResponse(status_code=404, content={'detail': str(exc)})

@app.exception_handler(RequestException)
async def network_error(request, exc):
    return JSONResponse(status_code=502, content={'detail': 'Could not reach Spotify. Please try again.'})

app.include_router(auth.router)
app.include_router(routes.router)

@app.get('/api/health')
def health():
    return {'status': 'ok'}

# A built frontend can run on the same local origin as the API.
frontend_dist = BACKEND_DIR.parent / 'frontend' / 'dist'
if frontend_dist.is_dir():
    app.mount('/', StaticFiles(directory=frontend_dist, html=True), name='frontend')
