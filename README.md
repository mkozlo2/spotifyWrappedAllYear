# Soundprint

Soundprint is a local, single-account Spotify listening analytics API. Connect a Spotify account to inspect top artists and tracks, collect listening history, and save snapshots for comparing rankings over time.

> **Project status:** The backend API is implemented. A frontend is not included yet; the `frontend` directory currently contains no tracked source files.

## Features

- Spotify OAuth login and logout
- Top artists and tracks for short-, medium-, and long-term ranges
- Recently played tracks and locally collected listening history
- Saved artist and track snapshots, with comparisons and ranking trends
- Listening activity grouped by date and hour in an IANA timezone
- SQLite storage by default
- Interactive API documentation at `/docs`

Listening history and play counts cover only events collected by this app; they are not a complete record of Spotify listening.

## Requirements

- Python 3.10 or newer
- A Spotify account and a Spotify app created in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

## Run locally

### 1. Set up the backend

In PowerShell, from the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell prevents virtual environment activation, either adjust your local execution policy or run the environment's Python directly with `.venv\Scripts\python.exe`.

### 2. Configure Spotify OAuth

In the Spotify Developer Dashboard, add this redirect URI to your Spotify app:

```text
http://127.0.0.1:8001/auth/callback
```

Edit `backend/.env` and set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` from your Spotify app. Generate a session secret and set it as `SESSION_SECRET`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep `.env` and your Spotify client secret private. The default `FRONTEND_URL` is `http://127.0.0.1:5173`; it can be changed to the origin of your frontend. The default SQLite database is created at `backend/spotify_wrapped.db`.

### 3. Start the API

From the `backend` directory, with the virtual environment active:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- Health check: <http://127.0.0.1:8001/api/health>
- Interactive API docs: <http://127.0.0.1:8001/docs>
- OAuth login: <http://127.0.0.1:8001/auth/login>

API endpoints other than health and authentication status require a connected Spotify session.

## Tests

From the `backend` directory, install the development dependencies and run the test suite:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Configuration

The backend reads settings from environment variables and `backend/.env`. See [`backend/.env.example`](backend/.env.example) for the available settings and defaults. To use a non-default database, set `DATABASE_URL` to a SQLAlchemy SQLite URL, for example:

```text
DATABASE_URL=sqlite:///C:/path/to/spotify_wrapped.db
```
