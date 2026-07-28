from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.db import Base, engine, SessionLocal
from app.models import Bookmark
from sqlalchemy import select


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.mark.parametrize("update_data", [
    {"title": "New title"}, {"title": "Example"}, {"url": "https://example.com/"},
    {"url": "https://new.com/"},
    {"title": "A", "url": "https://a.com/"}, {}
])
def test_partial_updates(reset_db, update_data):

    response_from_post = client.post('/bookmarks', json={'title': "Example",
                                                         'url': "https://example.com",
                                                         'tags': []})

    old_data = response_from_post.json()

    response = client.patch(f'/bookmarks/{old_data["id"]}', json=update_data)
    assert response.status_code == 204
    assert response.content == b""

    with SessionLocal() as db:
        db_bookmark = db.execute(select(Bookmark).where(Bookmark.id == old_data['id'])).scalar_one()

    for key in ['title', 'url']:
        if key not in update_data:
            assert getattr(db_bookmark, key) == old_data[key]
        else:
            assert getattr(db_bookmark, key) == update_data[key]


def test_update_not_existing_bookmark(reset_db):
    response = client.patch(f'/bookmarks/{999}', json={"title": "test"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Bookmark not found"}


@pytest.mark.parametrize("invalid_data_for_patch", [
    {"title": ""}, {"title": 123}, {"url": ['hello']},
    {"url": "Not url"},
    {"title": "  ", "url": " .com"},
    {"title": "Valid title", "url": "Not url"},
    {"title": "  ", "url": "https://valid_url.com"}
])
def test_patch_returns_422_for_invalid_data(reset_db, invalid_data_for_patch):
    response_from_post = client.post('/bookmarks', json={'title': "Example",
                                                         'url': "https://example.com",
                                                         'tags': []})

    old_data = response_from_post.json()

    response = client.patch(f'/bookmarks/{old_data["id"]}', json=invalid_data_for_patch)
    assert response.status_code == 422
    assert "detail" in response.json()

    with SessionLocal() as db:
        db_bookmark = db.execute(select(Bookmark).where(Bookmark.id == old_data['id'])).scalar_one()

    assert db_bookmark.title == old_data["title"]
    assert db_bookmark.url == old_data["url"]
