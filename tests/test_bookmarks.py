from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.db import Base, engine, SessionLocal
from app.models import Bookmark
from  pydantic import HttpUrl


client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


#POST

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
        assert set(data["tags"]) == set(create_data["tags"])

    with SessionLocal() as db:
        bookmarks = db.query(Bookmark).all()
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
        bookmarks = db.query(Bookmark).filter(Bookmark.url == 'https://fastapi.com/').all()
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


#GET

def test_get_empty_bookmarks(reset_db):
    response = client.get("/bookmarks")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_one_bookmark(reset_db):
    client.post("/bookmarks",json={"title": "FastAPI",
                                    "url": "https://fastapi.com/",
                                    "tags": ["python", "dev", "api"]})

    response = client.get("/bookmarks")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

    bookmark = data[0]
    assert isinstance(bookmark, dict)
    assert bookmark.keys() >= {'title', 'url', 'tags'}
    assert bookmark['title'] == "FastAPI"
    assert bookmark['url'] == "https://fastapi.com/"
    assert set(bookmark['tags']) == {"python", "dev", "api"}


def normalize(bookmark):
    return {"title": bookmark["title"],
            "url": str(HttpUrl(bookmark["url"])),
            "tags": set(bookmark["tags"])}


@pytest.fixture
def created_bookmarks(reset_db):
    bookmarks = [{'title': 'FastAPI', 'url': "https://fastapi.com/", 'tags': ['api', 'python', 'dev']},
                 {'title': 'SQLAlchemy', 'url': "https://sqlalchemy.com/", 'tags': ['python', 'database']},
                 {'title': 'Example', 'url': "https://example.com/", 'tags': []}]

    for bookmark in bookmarks:
        client.post("/bookmarks", json=bookmark)
    return [normalize(bookmark) for bookmark in bookmarks]


def test_get_multiple_bookmarks(created_bookmarks):
    response = client.get('/bookmarks')
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3

    actual_bookmarks = [{'title': bookmark['title'],
                        'url': bookmark['url'],
                        'tags': set(bookmark['tags'])} for bookmark in data]

    assert created_bookmarks == actual_bookmarks


#PATCH

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
        db_bookmark = db.query(Bookmark).filter(Bookmark.id==old_data['id']).first()

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
        db_bookmark = db.query(Bookmark).filter(Bookmark.id == old_data['id']).first()

    assert db_bookmark.title == old_data["title"]
    assert db_bookmark.url == old_data["url"]


#DELETE

def test_delete_bookmark_if_exists(reset_db):
    response_from_post = client.post('/bookmarks',  json={"title": "Example",
                                                            "url": "https://example.com",
                                                            "tags": ["eхample", "test", "python"] })
    assert response_from_post.status_code == 201

    data = response_from_post.json()
    bookmark_id = data["id"]
    response = client.delete(f'/bookmarks/{bookmark_id}')
    assert response.status_code == 204
    assert response.content == b""

    with SessionLocal() as db:
        assert db.query(Bookmark).filter(Bookmark.id==bookmark_id).first() is None


def test_delete_bookmark_if_not_exists(reset_db):
    response = client.delete(f'/bookmarks/{9999}')
    assert response.status_code == 404
    assert response.json() == {"detail": "Bookmark not found"}

    


























