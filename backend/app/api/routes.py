from datetime import date
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, Query
from spotipy.exceptions import SpotifyException
from app.api import schemas as s
from app.api.auth import require_session
from app.services import spotify_service as spotify, analytics_service as analytics
from app.repositories import spotify_repository as repo
from app.spotify.client import get_spotify_client

router = APIRouter(prefix='/api', dependencies=[Depends(require_session)])
sync_lock = Lock()

@router.get('/me', response_model=s.Profile)
def me():
    return spotify.fetch_profile()

@router.get('/top-artists', response_model=s.TopArtists)
def top_artists(time_range: s.TimeRange = 'medium_term', limit: int = Query(20, ge=1, le=50)):
    return spotify.fetch_top_artists(time_range, limit)

@router.get('/top-tracks', response_model=s.TopTracks)
def top_tracks(time_range: s.TimeRange = 'medium_term', limit: int = Query(20, ge=1, le=50)):
    return spotify.fetch_top_tracks(time_range, limit)

@router.get('/recently-played', response_model=s.Recent)
def recently_played():
    return spotify.fetch_recently_played()

@router.get('/history', response_model=s.History)
def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return repo.list_events(limit, offset)

@router.post('/snapshots/{kind}', response_model=s.SnapshotSaved, status_code=201)
def create_snapshot(kind: s.Kind, time_range: s.TimeRange = 'medium_term', limit: int = Query(50, ge=1, le=50)):
    return repo.save_snapshot(spotify.fetch_top(kind, time_range, limit), kind)

@router.get('/snapshots', response_model=list[s.Snapshot])
def snapshots(kind: s.Kind | None = None, time_range: s.TimeRange | None = None,
              limit: int = Query(100, ge=1, le=500)):
    return repo.list_snapshots(kind, time_range, limit)

@router.get('/snapshots/artists', response_model=list[s.Snapshot])
def artist_snapshots(time_range: s.TimeRange | None = None):
    return repo.list_snapshots('artists', time_range)

@router.get('/snapshots/tracks', response_model=list[s.Snapshot])
def track_snapshots(time_range: s.TimeRange | None = None):
    return repo.list_snapshots('tracks', time_range)

@router.get('/snapshots/compare', response_model=s.Comparison)
def compare(before_id: int, after_id: int):
    return analytics.compare(before_id, after_id)

@router.get('/analytics/overview', response_model=s.Overview)
def overview(time_range: s.TimeRange = 'medium_term'):
    return analytics.overview(time_range)

@router.get('/analytics/genres', response_model=list[s.Genre])
def genres(time_range: s.TimeRange = 'medium_term'):
    return analytics.overview(time_range)['genres']

@router.get('/analytics/listening', response_model=s.Listening)
def listening(tz: str = 'UTC', start: date | None = None, end: date | None = None):
    return analytics.listening(tz, start, end)

@router.get('/analytics/trends', response_model=s.Trends)
def trends(kind: s.Kind = 'artists', time_range: s.TimeRange = 'medium_term'):
    return analytics.trends(kind, time_range)

@router.post('/sync', response_model=s.SyncResult)
def sync(time_range: s.TimeRange = 'medium_term'):
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(409, 'A sync is already running.')
    try:
        # Validate account identity even if the cache was replaced manually.
        repo.bind_account(spotify.fetch_profile()['id'])
        saved, warnings = [], []
        for kind in ('artists', 'tracks'):
            try:
                saved.append(repo.save_snapshot(spotify.fetch_top(kind, time_range, 50), kind))
            except SpotifyException as exc:
                if exc.http_status != 403:
                    raise
                warnings.append(f'{kind.title()} unavailable for this Spotify application.')
        try:
            recent = spotify.fetch_recently_played()
            count = repo.save_events(recent['items'])
        except SpotifyException as exc:
            if exc.http_status != 403:
                raise
            recent = {'total': 0, 'page_limit_reached': False}
            count = 0
            warnings.append('Recently played unavailable. Reconnect to grant the history permission.')
        return {'saved_events': count, 'fetched_events': recent['total'],
                'page_limit_reached': recent['page_limit_reached'], 'snapshots': saved, 'warnings': warnings}
    finally:
        sync_lock.release()

@router.get('/artists/{spotify_id}', response_model=s.Artist)
def artist(spotify_id: str):
    return spotify.transform_artist(get_spotify_client().artist(spotify_id))

@router.get('/tracks/{spotify_id}', response_model=s.Track)
def track(spotify_id: str):
    return spotify.transform_track(get_spotify_client().track(spotify_id))

@router.get('/albums/{spotify_id}', response_model=s.Album)
def album(spotify_id: str):
    value = get_spotify_client().album(spotify_id)
    return {'id': value['id'], 'name': value['name'], 'image_url': spotify.image_url(value.get('images', [])),
            'release_date': value.get('release_date'), 'spotify_url': value.get('external_urls', {}).get('spotify', ''),
            'artists': [a['name'] for a in value.get('artists', [])]}
