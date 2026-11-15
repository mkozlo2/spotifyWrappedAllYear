from app.spotify.client import get_spotify_client


def image_url(images):
    return images[0]['url'] if images else None


def transform_artist(artist):
    return {'id': artist['id'], 'name': artist['name'], 'genres': artist.get('genres', []),
            'popularity': artist.get('popularity'), 'followers': artist.get('followers', {}).get('total'),
            'image_url': image_url(artist.get('images', [])),
            'spotify_url': artist.get('external_urls', {}).get('spotify', '')}


def transform_track(track):
    album = track.get('album') or {}
    return {'id': track['id'], 'name': track['name'],
            'artists': [{'id': a['id'], 'name': a['name'],
                         'spotify_url': a.get('external_urls', {}).get('spotify', '')}
                        for a in track.get('artists', []) if a.get('id')],
            'album': album.get('name', ''), 'duration_ms': track.get('duration_ms', 0),
            'cover_url': image_url(album.get('images', [])),
            'spotify_url': track.get('external_urls', {}).get('spotify', ''),
            'release_date': album.get('release_date'), 'explicit': track.get('explicit', False)}


def fetch_top(kind, time_range, limit):
    spotify = get_spotify_client()
    method = spotify.current_user_top_artists if kind == 'artists' else spotify.current_user_top_tracks
    transform = transform_artist if kind == 'artists' else transform_track
    items = [dict(transform(item), rank=rank) for rank, item in
             enumerate(method(limit=limit, time_range=time_range)['items'], 1) if item and item.get('id')]
    return {'time_range': time_range, 'total': len(items), 'items': items}


def fetch_top_tracks(time_range, limit):
    return fetch_top('tracks', time_range, limit)


def fetch_top_artists(time_range, limit):
    return fetch_top('artists', time_range, limit)


def fetch_profile():
    user = get_spotify_client().current_user()
    return {'id': user['id'], 'display_name': user.get('display_name') or user['id'],
            'image_url': image_url(user.get('images', [])),
            'spotify_url': user.get('external_urls', {}).get('spotify', '')}


def fetch_recently_played(max_pages=20):
    """Walk backwards through available cursor pages, never promise a full history."""
    spotify = get_spotify_client()
    events, cursors, before = [], set(), None
    truncated = False
    for _ in range(max_pages):
        page = spotify.current_user_recently_played(limit=50, **({'before': before} if before else {}))
        for item in page.get('items', []):
            track = item.get('track')
            if track and track.get('id') and not track.get('is_local'):
                events.append({'played_at': item['played_at'], 'track': transform_track(track)})
        cursor = (page.get('cursors') or {}).get('before')
        if not page.get('next') or not cursor or cursor in cursors or not page.get('items'):
            break
        cursors.add(cursor)
        before = int(cursor)
    else:
        truncated = True
    return {'items': events, 'total': len(events), 'page_limit_reached': truncated,
            'coverage': 'Only recent events Spotify makes available; gaps cannot be recovered reliably.'}
