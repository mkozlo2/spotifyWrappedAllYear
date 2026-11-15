
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    genres: Mapped[list] = mapped_column(JSON, default=list)
    popularity: Mapped[int | None] = mapped_column(Integer)
    followers: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String)
    spotify_url: Mapped[str] = mapped_column(String)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    album: Mapped[str] = mapped_column(String)
    duration_ms: Mapped[int] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(String)
    spotify_url: Mapped[str] = mapped_column(String)
    release_date: Mapped[str | None] = mapped_column(String)
    explicit: Mapped[bool] = mapped_column(Boolean)


class TrackArtist(Base):
    __tablename__ = "track_artists"

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True
    )

    artist_id: Mapped[str] = mapped_column(
        ForeignKey("artists.id"),
        primary_key=True
    )

    position: Mapped[int] = mapped_column(Integer)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    time_range: Mapped[str] = mapped_column(String, nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)


class SnapshotArtist(Base):
    __tablename__ = "snapshot_artists"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        primary_key=True
    )

    artist_id: Mapped[str] = mapped_column(
        ForeignKey("artists.id"),
        primary_key=True
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "rank"),
    )


class SnapshotTrack(Base):
    __tablename__ = "snapshot_tracks"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        primary_key=True
    )

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id"),
        primary_key=True
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "rank"),
    )


class SnapshotPayload(Base):
    """Immutable metadata alongside the original normalized ranking tables."""
    __tablename__ = "snapshot_payloads"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True)
    items: Mapped[list] = mapped_column(JSON, nullable=False)


class ListeningEvent(Base):
    __tablename__ = "listening_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), index=True)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Preserve names, artists and artwork as observed at collection time.
    track: Mapped[dict] = mapped_column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("track_id", "played_at"),)


class LocalAccount(Base):
    """One account per local database; prevents mixing another account's history."""
    __tablename__ = "local_account"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    spotify_id: Mapped[str] = mapped_column(String, nullable=False)
