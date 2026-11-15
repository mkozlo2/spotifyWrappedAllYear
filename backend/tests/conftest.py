import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"

from app.database.connection import Base
from app.repositories import spotify_repository as repo
from app.services.spotify_service import transform_track

@pytest.fixture(autouse=True)
def database(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    from sqlalchemy import event
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(repo, 'SessionLocal', sessionmaker(bind=engine))
    from app import main
    monkeypatch.setattr(main, 'engine', engine)
    yield
    engine.dispose()

@pytest.fixture
def artist():
    return {'id': 'a', 'name': 'Artist', 'spotify_url': '', 'genres': ['pop'], 'rank': 1}

@pytest.fixture
def track():
    return transform_track({'id': 't', 'name': 'Track', 'duration_ms': 123000,
        'artists': [{'id': 'a', 'name': 'Artist'}], 'album': {'name': 'Album'}}) | {'rank': 1}

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.auth import require_session
    app.dependency_overrides[require_session] = lambda: None
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()
