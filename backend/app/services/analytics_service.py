from collections import Counter
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.repositories import spotify_repository as repo


def genres(items):
    counts = Counter(g for a in items for g in a.get('genres', []))
    total = sum(counts.values())
    return [{'name': name, 'count': count, 'percent': round(count * 100 / total, 1)}
            for name, count in counts.most_common()]


def overview(time_range):
    artists = repo.list_snapshots('artists', time_range, 1)
    tracks = repo.list_snapshots('tracks', time_range, 1)
    a = artists[0]['items'] if artists else []
    t = tracks[0]['items'] if tracks else []
    history = repo.list_events(8)
    snapshots = repo.list_snapshots(limit=1)
    return {'top_artist': a[0] if a else None, 'top_track': t[0] if t else None,
            'collected_events': history['total'], 'recent_events': history['items'],
            'latest_snapshot': snapshots[0]['captured_at'] if snapshots else None,
            'genres': genres(a), 'average_duration_ms': round(sum(x['duration_ms'] for x in t) / len(t)) if t else None,
            'explicit': sum(bool(x.get('explicit')) for x in t),
            'non_explicit': sum(not x.get('explicit') for x in t),
            'ranked_tracks': len(t), 'time_range': time_range,
            'coverage': 'Rankings reflect Spotify affinity. Play counts cover collected events only.'}


def listening(tz='UTC', start=None, end=None):
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise ValueError('Unknown IANA timezone.')
    if start and end and start > end:
        raise ValueError('Start date must be before end date.')
    events = repo.all_events()
    selected = [e for e in events if (not start or e['played_at'].astimezone(zone).date() >= start)
                and (not end or e['played_at'].astimezone(zone).date() <= end)]
    days = Counter(e['played_at'].astimezone(zone).date().isoformat() for e in selected)
    hours = Counter(e['played_at'].astimezone(zone).hour for e in selected)
    artists, names = Counter(), {}
    for event in selected:
        for a in {a['id']: a for a in event['track']['artists']}.values():
            artists[a['id']] += 1
            names[a['id']] = a['name']
    return {'total': len(selected), 'timezone': tz,
            'by_day': [{'date': day, 'count': count} for day, count in sorted(days.items())],
            'by_hour': [{'hour': hour, 'count': hours[hour]} for hour in range(24)],
            'artists': [{'id': key, 'name': names[key], 'count': count} for key, count in artists.most_common(20)],
            'first_collected': events[0]['played_at'].isoformat() if events else None,
            'last_collected': events[-1]['played_at'].isoformat() if events else None,
            'coverage': 'Observed listening events only, with possible gaps. Track duration is not listening time.'}


def compare(before_id, after_id):
    before, after = repo.get_snapshot(before_id), repo.get_snapshot(after_id)
    if not before or not after:
        raise LookupError('Snapshot not found.')
    if before['item_type'] != after['item_type'] or before['time_range'] != after['time_range']:
        raise ValueError('Compare snapshots of the same item type and time range.')
    if (before['captured_at'], before['id']) >= (after['captured_at'], after['id']):
        raise ValueError('Choose an earlier baseline snapshot.')
    old, new = ({i['id']: i for i in s['items']} for s in (before, after))
    rows = []
    for key in dict.fromkeys([*new, *old]):
        previous, current = old.get(key), new.get(key)
        rows.append({'id': key, 'name': (current or previous)['name'],
            'previous_rank': previous['rank'] if previous else None,
            'current_rank': current['rank'] if current else None,
            'change': previous['rank'] - current['rank'] if previous and current else None,
            'status': 'new' if not previous else 'dropped' if not current else 'retained'})
    old_genres, new_genres = genres(before['items']), genres(after['items'])
    old_map, new_map = ({g['name']: g['percent'] for g in values} for values in (old_genres, new_genres))
    return {'before_id': before_id, 'after_id': after_id, 'items': rows,
            'genres': [{'name': name, 'before': old_map.get(name, 0), 'after': new_map.get(name, 0)}
                       for name in sorted(old_map.keys() | new_map.keys())],
            'coverage': 'New means newly present in this ranking, not first-ever listened. Dropped means outside the collected list.'}


def trends(kind, time_range):
    snapshots = list(reversed(repo.list_snapshots(kind, time_range)))
    counts, names = Counter(), {}
    for s in snapshots:
        for item in s['items']:
            counts[item['id']] += 1
            names[item['id']] = item['name']
    consistent = counts.most_common(1)
    return {'snapshots': snapshots,
            'consistent_favorite': {'name': names[consistent[0][0]], 'appearances': consistent[0][1]} if consistent else None,
            'comparison': compare(snapshots[-2]['id'], snapshots[-1]['id']) if len(snapshots) > 1 else None}
