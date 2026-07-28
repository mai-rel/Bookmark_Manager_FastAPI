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


def test_delete_bookmark_if_exists(reset_db):
    response_from_post = client.post('/bookmarks',  json={"title": "Example",
                                                          "url": "https://example.com",
                                                          "tags": ["ехample", "test", "python"]})
    assert response_from_post.status_code == 201

    data = response_from_post.json()
    bookmark_id = data["id"]
    response = client.delete(f'/bookmarks/{bookmark_id}')
    assert response.status_code == 204
    assert response.content == b""

    with SessionLocal() as db:
        assert db.execute(select(Bookmark).where(Bookmark.id == bookmark_id)).scalar_one_or_none() is None


def test_delete_bookmark_if_not_exists(reset_db):
    response = client.delete(f'/bookmarks/{9999}')
    assert response.status_code == 404
    assert response.json() == {"detail": "Bookmark not found"}
