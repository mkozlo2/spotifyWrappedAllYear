"""Transactional persistence; Spotify calls belong in the service layer."""
from datetime import datetime, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.sqlite import insert
from app.database.connection import SessionLocal
from app.database.models import (Artist, Track, TrackArtist, Snapshot,
    SnapshotArtist, SnapshotTrack, SnapshotPayload, ListeningEvent, LocalAccount)


def upsert_artist(db, data):
    artist = db.get(Artist, data['id'])
    if artist is None:
        artist = Artist(id=data['id'], name=data['name'], spotify_url=data.get('spotify_url', ''))
        db.add(artist)
    for key in ('name', 'genres', 'popularity', 'followers', 'image_url', 'spotify_url'):
        if key in data:
            setattr(artist, key, data[key])
    db.flush()


def upsert_track(db, data):
    fields = ('id', 'name', 'album', 'duration_ms', 'cover_url', 'spotify_url', 'release_date', 'explicit')
    db.merge(Track(**{key: data.get(key) for key in fields}))
    db.flush()
    db.execute(delete(TrackArtist).where(TrackArtist.track_id == data['id']))
    for position, artist in enumerate(data['artists'], 1):
        upsert_artist(db, artist)
        db.add(TrackArtist(track_id=data['id'], artist_id=artist['id'], position=position))
    db.flush()


def save_snapshot(data, kind):
    with SessionLocal.begin() as db:
        latest = db.scalar(select(Snapshot).where(Snapshot.item_type == kind,
            Snapshot.time_range == data['time_range']).order_by(Snapshot.id.desc()))
        # Coalesce repeated identical collections on the same UTC day only.
        payload = db.get(SnapshotPayload, latest.id) if latest else None
        if payload and payload.items == data['items'] and latest.captured_at.date() == datetime.now(timezone.utc).date():
            return {'snapshot_id': latest.id, 'saved': len(payload.items), 'item_type': kind, 'reused': True}
        snapshot = Snapshot(time_range=data['time_range'], item_type=kind)
        db.add(snapshot)
        db.flush()
        for item in data['items']:
            if kind == 'artists':
                upsert_artist(db, item)
                db.add(SnapshotArtist(snapshot_id=snapshot.id, artist_id=item['id'], rank=item['rank']))
            else:
                upsert_track(db, item)
                db.add(SnapshotTrack(snapshot_id=snapshot.id, track_id=item['id'], rank=item['rank']))
        db.add(SnapshotPayload(snapshot_id=snapshot.id, items=data['items']))
        return {'snapshot_id': snapshot.id, 'saved': len(data['items']), 'item_type': kind, 'reused': False}


def save_top_artists(data):
    return save_snapshot(data, 'artists')


def save_top_tracks(data):
    return save_snapshot(data, 'tracks')


def snapshot_dict(db, snapshot):
    payload = db.get(SnapshotPayload, snapshot.id)
    if payload:
        items = payload.items
    else:
        # Compatibility with pre-existing snapshots; old metadata was not immutable.
        link, model, key = ((SnapshotArtist, Artist, 'artist_id') if snapshot.item_type == 'artists'
                            else (SnapshotTrack, Track, 'track_id'))
        rows = db.execute(select(link, model).join(model, model.id == getattr(link, key))
            .where(link.snapshot_id == snapshot.id).order_by(link.rank)).all()
        items = []
        for ranking, item in rows:
            value = {c.name: getattr(item, c.name) for c in model.__table__.columns}
            value['rank'] = ranking.rank
            if snapshot.item_type == 'tracks':
                value['artists'] = [{'id': a.id, 'name': a.name, 'spotify_url': a.spotify_url}
                    for a in db.scalars(select(Artist).join(TrackArtist).where(TrackArtist.track_id == item.id)
                                        .order_by(TrackArtist.position))]
            items.append(value)
    return {'id': snapshot.id, 'captured_at': snapshot.captured_at.replace(tzinfo=timezone.utc).isoformat(),
            'item_type': snapshot.item_type, 'time_range': snapshot.time_range, 'items': items,
            'metadata_preserved': payload is not None}


def list_snapshots(kind=None, time_range=None, limit=100):
    with SessionLocal() as db:
        query = select(Snapshot)
        if kind:
            query = query.where(Snapshot.item_type == kind)
        if time_range:
            query = query.where(Snapshot.time_range == time_range)
        return [snapshot_dict(db, s) for s in db.scalars(query.order_by(Snapshot.id.desc()).limit(limit))]


def get_snapshot(snapshot_id):
    with SessionLocal() as db:
        snapshot = db.get(Snapshot, snapshot_id)
        return snapshot_dict(db, snapshot) if snapshot else None


def save_events(events):
    saved = 0
    with SessionLocal.begin() as db:
        for event in events:
            track = event['track']
            upsert_track(db, track)
            result = db.execute(insert(ListeningEvent).values(track_id=track['id'],
                played_at=datetime.fromisoformat(event['played_at'].replace('Z', '+00:00')).astimezone(timezone.utc),
                track=track).on_conflict_do_nothing(index_elements=['track_id', 'played_at']))
            saved += result.rowcount
    return saved


def list_events(limit=100, offset=0):
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(ListeningEvent))
        rows = db.scalars(select(ListeningEvent).order_by(ListeningEvent.played_at.desc(), ListeningEvent.id.desc())
                          .offset(offset).limit(limit))
        return {'total': total, 'items': [{'id': e.id, 'played_at': e.played_at.replace(tzinfo=timezone.utc).isoformat(),
                                          'track': e.track} for e in rows]}


def all_events():
    with SessionLocal() as db:
        return [{'played_at': e.played_at.replace(tzinfo=timezone.utc), 'track': e.track}
                for e in db.scalars(select(ListeningEvent).order_by(ListeningEvent.played_at))]


def bind_account(spotify_id):
    with SessionLocal.begin() as db:
        account = db.get(LocalAccount, 1)
        if account and account.spotify_id != spotify_id:
            raise ValueError('This local database belongs to a different Spotify account. Use a separate DATABASE_URL.')
        if not account:
            db.add(LocalAccount(id=1, spotify_id=spotify_id))
