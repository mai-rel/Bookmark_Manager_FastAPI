from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.db import Base, engine, SessionLocal
from app.models import Bookmark
from  pydantic import HttpUrl
import time
from sqlalchemy import select


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


@pytest.mark.parametrize('query_params', [{'query_title': 'api'}, {'query_title': 'python'},
                                          {'query_tags': ['python']}, {'query_tags': ['Python']},
                                          {'query_title': 'api', 'query_tags': ['database']},
                                          {'query_tags': ['not_exist']}, {'query_tags': ['api', 'database']}])

def test_get_bookmarks_with_query_params(query_params, created_bookmarks):
    expected_bookmarks = set()
    query_title = query_params.get('query_title', None)
    query_tags = query_params.get('query_tags', None)

    for bookmark in created_bookmarks:
        if query_title and query_title.lower() in bookmark['title'].lower():
            if not query_tags or any(tag.lower() in bookmark['tags'] for tag in query_tags):
                expected_bookmarks.add((bookmark['title'], bookmark['url'], frozenset(bookmark['tags'])))

        elif not query_title:
            if query_tags and any(tag.lower() in bookmark['tags'] for tag in query_tags):
                expected_bookmarks.add((bookmark['title'], bookmark['url'], frozenset(bookmark['tags'])))

    response = client.get('/bookmarks', params=query_params)
    assert response.status_code == 200

    data = response.json()
    actual_bookmarks = {(bookmark['title'], bookmark['url'], frozenset(bookmark['tags'])) for bookmark in data}
    assert expected_bookmarks == actual_bookmarks


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
        assert db.execute(select(Bookmark).where(Bookmark.id == bookmark_id)).scalar_one_or_none() is None


def test_delete_bookmark_if_not_exists(reset_db):
    response = client.delete(f'/bookmarks/{9999}')
    assert response.status_code == 404
    assert response.json() == {"detail": "Bookmark not found"}



def test_bookmark_timestamps_are_set_on_create_and_updated_on_patch(reset_db):
    response_from_post = client.post('/bookmarks', json={"title": "FastAPI",
                                               "url": "https://fastapi.com/",
                                               "tags": ["python", "dev", "api"]})

    assert response_from_post.status_code == 201

    created_bookmark = response_from_post.json()
    bookmark_id = created_bookmark['id']
    assert 'created_at' in created_bookmark and 'updated_at' in created_bookmark
    assert  created_bookmark['created_at'] == created_bookmark['updated_at']

    with SessionLocal() as db:
        db_bookmark = db.get(Bookmark, bookmark_id)
        assert hasattr(db_bookmark, 'created_at') and hasattr(db_bookmark, 'updated_at')
        assert db_bookmark.created_at == db_bookmark.updated_at

    time.sleep(3)

    response_from_patch = client.patch(f'/bookmarks/{bookmark_id}', json={'title': 'Updated FastAPI'})
    assert response_from_patch.status_code == 204

    with SessionLocal() as db:
        updated_bookmark = db.get(Bookmark, bookmark_id)
        assert db_bookmark.created_at == updated_bookmark.created_at
        assert db_bookmark.updated_at != updated_bookmark.updated_at



@pytest.mark.parametrize("sorting_params", [{"sort": "random"},
                                           {"sort": "title", "order": "abc"}])
def test_sorting_bookmarks_not_valid_params(created_bookmarks, sorting_params):
    response = client.get('/bookmarks', params=sorting_params)

    assert response.status_code == 400
    assert "detail" in response.json()



@pytest.mark.parametrize("sorting_params", [{"sort": "title"},
                                            {"sort": "title", "order": "desc"}])
def test_correct_sorting_bookmarks_by_title(created_bookmarks, sorting_params):
    expected_bookmarks = [(bookmark["title"], bookmark["url"]) for bookmark in created_bookmarks]
    flag = sorting_params.get("order", None) == "desc"
    expected_bookmarks.sort(reverse=flag)

    response = client.get('/bookmarks', params=sorting_params)
    assert response.status_code == 200

    data = response.json()
    actual_bookmarks = [(bookmark["title"], bookmark["url"]) for bookmark in data]

    assert expected_bookmarks == actual_bookmarks


@pytest.mark.parametrize("sorting_params", [{"sort": "created_at"},
                                            {"sort": "created_at", "order": "desc"},
                                            {"sort": "updated_at"}])

def test_sort_bookmarks_by_created_at_and_updated_at(created_bookmarks, sorting_params):
    expected_bookmarks = [(bookmark["title"], bookmark["url"]) for bookmark in created_bookmarks]

    if sorting_params["sort"] == 'updated_at':
        with SessionLocal() as db:
            bookmark_for_update = db.execute(select(Bookmark).where(Bookmark.url == 'https://fastapi.com/')).scalar_one()
            bookmark_id = bookmark_for_update.id

        time.sleep(1)

        response_from_patch = client.patch(f'/bookmarks/{bookmark_id}', json={"title": "Updated FastAPI"})
        assert response_from_patch.status_code == 204

        expected_bookmarks.remove(('FastAPI', 'https://fastapi.com/'))
        expected_bookmarks.append(('Updated FastAPI', 'https://fastapi.com/'))

    if sorting_params.get("order", None) == 'desc':
        expected_bookmarks.reverse()

    response = client.get("bookmarks/", params=sorting_params)
    assert response.status_code == 200

    actual_bookmarks = [(bookmark["title"], bookmark["url"]) for bookmark in response.json()]
    assert expected_bookmarks == actual_bookmarks
































