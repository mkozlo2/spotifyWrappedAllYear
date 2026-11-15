from app.repositories import spotify_repository as repo
from app.services import analytics_service as analytics
from app.services.spotify_service import transform_track
import pytest


def test_snapshot_roundtrip_and_dedup(track):
    data = {'time_range': 'short_term', 'items': [track]}
    result = repo.save_top_tracks(data)
    assert result['saved'] == 1
    assert repo.save_top_tracks(data)['reused'] is True
    assert repo.get_snapshot(result['snapshot_id'])['items'] == [track]


def test_history_duplicate_and_analytics(track):
    event = {'played_at': '2026-11-15T01:00:00Z', 'track': track}
    assert repo.save_events([event, event]) == 1
    assert repo.save_events([event]) == 0
    result = analytics.listening('America/New_York')
    assert result['total'] == 1
    assert result['by_day'] == [{'date': '2026-11-14', 'count': 1}]
    assert result['by_hour'][20]['count'] == 1
    assert result['artists'][0]['count'] == 1


def test_artist_metadata_preserved(artist, track):
    repo.save_top_artists({'time_range': 'short_term', 'items': [artist]})
    repo.save_top_tracks({'time_range': 'short_term', 'items': [track]})
    from app.database.models import Artist
    with repo.SessionLocal() as db:
        assert db.get(Artist, 'a').genres == ['pop']


def test_snapshot_comparison_and_immutable_genres(artist):
    first = repo.save_top_artists({'time_range': 'short_term', 'items': [artist]})
    second = repo.save_top_artists({'time_range': 'short_term', 'items': [artist | {'rank': 2, 'genres': ['rock']},
        artist | {'id': 'b', 'name': 'New', 'rank': 1}]})
    result = analytics.compare(first['snapshot_id'], second['snapshot_id'])
    assert result['items'][0]['change'] == -1
    assert result['items'][1]['status'] == 'new'
    assert repo.get_snapshot(first['snapshot_id'])['items'][0]['genres'] == ['pop']


def test_transform_missing_optional_fields(track):
    assert track['artists'][0]['id'] == 'a'
    assert track['cover_url'] is None
    assert track['explicit'] is False


def test_account_isolation():
    repo.bind_account('one')
    repo.bind_account('one')
    with pytest.raises(ValueError):
        repo.bind_account('two')


def test_empty_analytics():
    assert analytics.overview('short_term')['average_duration_ms'] is None
    assert analytics.listening()['total'] == 0
    with pytest.raises(ValueError):
        analytics.listening('invalid/zone')
