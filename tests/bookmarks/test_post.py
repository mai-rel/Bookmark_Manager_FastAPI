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


@pytest.mark.parametrize("create_data", [
    {"title": "FastAPI", "url": "https://fastapi.com/", "tags": ["python", "dev", "api"]},
    {"title": "FastAPI", "url": "https://fastapi.com/"}])
def test_create_bookmark_success_with_tags_or_without(reset_db, create_data):
    response = client.post("/bookmarks", json=create_data)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["title"] == create_data["title"]
    assert data["url"] == create_data["url"]

    if "tags" not in create_data:
        assert data["tags"] == []
    else:
        assert {tag['name'] for tag in data["tags"]} == set(create_data["tags"])

    with SessionLocal() as db:
        bookmarks = db.execute(select(Bookmark)).scalars().all()
        assert len(bookmarks) == 1

        bookmark = bookmarks[0]
        assert bookmark.title == create_data["title"]
        assert bookmark.url == create_data["url"]

        if "tags" not in create_data:
            assert bookmark.tags == []
        else:
            actual_tag_names = {tag.name for tag in bookmark.tags}
            expected_tag_names = set(create_data["tags"])
            assert actual_tag_names == expected_tag_names


def test_create_bookmark_with_existing_url(reset_db):
    client.post("/bookmarks", json={"title": "FastAPI",
                                    "url": "https://fastapi.com/",
                                    "tags": ["python", "dev", "api"]})

    response = client.post("/bookmarks", json={"title": "Fast API",
                                               "url": "https://fastapi.com/",
                                               "tags": ["python", "dev", "api"]})

    assert response.status_code == 409

    with SessionLocal() as db:
        bookmarks = db.execute(select(Bookmark).where(Bookmark.url == 'https://fastapi.com/')).scalars().all()
        assert len(bookmarks) == 1


@pytest.mark.parametrize("invalid_data_for_post", [
    {"title": '', "url": "https://fastapi.com/", "tags": ["python", "dev", "api"]},
    {"title": 'FastAPI', "url": "fastapi.com", "tags": []},
    {"title": 'FastAPI', "url": "https://fastapi.com/", "tags": [123, 'python']},
    {"url": "https://fastapi.com/", "tags": ['api']},
    {"tags": ['api', 'dev']}])
def test_create_bookmark_with_invalid_data(reset_db, invalid_data_for_post):
    response = client.post("/bookmarks", json=invalid_data_for_post)
    assert response.status_code == 422
