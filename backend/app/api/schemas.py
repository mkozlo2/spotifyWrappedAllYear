"""Public API contracts. Tokens and ORM objects never cross this boundary."""
from typing import Literal
from pydantic import BaseModel, Field

TimeRange = Literal['short_term', 'medium_term', 'long_term']
Kind = Literal['artists', 'tracks']

class ArtistRef(BaseModel):
    id: str
    name: str
    spotify_url: str = ''

class Artist(ArtistRef):
    genres: list[str] = Field(default_factory=list)
    popularity: int | None = None
    followers: int | None = None
    image_url: str | None = None
    rank: int | None = None

class Track(BaseModel):
    id: str
    name: str
    artists: list[ArtistRef]
    album: str
    duration_ms: int
    cover_url: str | None = None
    spotify_url: str = ''
    release_date: str | None = None
    explicit: bool
    rank: int | None = None

class TopArtists(BaseModel):
    time_range: TimeRange
    total: int
    items: list[Artist]

class TopTracks(BaseModel):
    time_range: TimeRange
    total: int
    items: list[Track]

class Event(BaseModel):
    id: int | None = None
    played_at: str
    track: Track

class History(BaseModel):
    total: int
    items: list[Event]

class Recent(History):
    coverage: str
    page_limit_reached: bool

class Snapshot(BaseModel):
    id: int
    captured_at: str
    item_type: Kind
    time_range: TimeRange
    items: list[Track | Artist]
    metadata_preserved: bool

class SnapshotSaved(BaseModel):
    snapshot_id: int
    saved: int
    item_type: Kind
    reused: bool

class Profile(BaseModel):
    id: str
    display_name: str
    image_url: str | None = None
    spotify_url: str

class Status(BaseModel):
    authenticated: bool
    configured: bool

class Genre(BaseModel):
    name: str
    count: int
    percent: float

class Overview(BaseModel):
    top_artist: Artist | None
    top_track: Track | None
    collected_events: int
    recent_events: list[Event]
    latest_snapshot: str | None
    genres: list[Genre]
    average_duration_ms: int | None
    explicit: int
    non_explicit: int
    ranked_tracks: int
    time_range: TimeRange
    coverage: str

class Daily(BaseModel):
    date: str
    count: int

class Hourly(BaseModel):
    hour: int
    count: int

class ArtistCount(BaseModel):
    id: str
    name: str
    count: int

class Listening(BaseModel):
    total: int
    timezone: str
    by_day: list[Daily]
    by_hour: list[Hourly]
    artists: list[ArtistCount]
    first_collected: str | None
    last_collected: str | None
    coverage: str

class RankChange(BaseModel):
    id: str
    name: str
    previous_rank: int | None
    current_rank: int | None
    change: int | None
    status: Literal['new', 'dropped', 'retained']

class GenreChange(BaseModel):
    name: str
    before: float
    after: float

class Comparison(BaseModel):
    before_id: int
    after_id: int
    items: list[RankChange]
    genres: list[GenreChange]
    coverage: str

class Favorite(BaseModel):
    name: str
    appearances: int

class Trends(BaseModel):
    snapshots: list[Snapshot]
    consistent_favorite: Favorite | None
    comparison: Comparison | None

class SyncResult(BaseModel):
    saved_events: int
    fetched_events: int
    page_limit_reached: bool
    snapshots: list[SnapshotSaved]
    warnings: list[str]

class Album(BaseModel):
    id: str
    name: str
    image_url: str | None
    release_date: str | None
    spotify_url: str
    artists: list[str]

class Message(BaseModel):
    message: str
