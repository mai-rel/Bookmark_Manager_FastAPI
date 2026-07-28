from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.db import Base, engine, SessionLocal
from app.models import Bookmark, Tag
from collections import defaultdict
from sqlalchemy import select


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.mark.parametrize("tags_for_post", [
    ["python", "dev", "api", "dev", "dev"],
    ["PYTHON", "Dev", "api", "DEV ", " dev"],
    ['', '   ']
])
def test_create_bookmark_normalizes_tags(reset_db, tags_for_post):
    response = client.post('/bookmarks', json={"title": "FastAPI",
                                               "url": "https://fastapi.com/",
                                               "tags": tags_for_post})

    assert response.status_code == 201
    data = response.json()

    expected_tag_names = {tag.strip().lower() for tag in tags_for_post if tag.strip()}
    expected_count = len(expected_tag_names)

    with SessionLocal() as db:
        db_bookmark = db.get(Bookmark, data["id"])
        assert len(db_bookmark.tags) == expected_count

        actual_names = {tag_obj.name for tag_obj in db_bookmark.tags}
        assert actual_names == expected_tag_names

        tags_in_db = db.query(Tag).all()
        assert len(tags_in_db) == expected_count
        tags_names_in_db = {tag_obj.name for tag_obj in tags_in_db}
        assert tags_names_in_db == expected_tag_names


def test_create_bookmarks_with_same_tags_does_not_duplicate_tags(reset_db):
    response1 = client.post("/bookmarks", json={"title": "FastAPI",
                                                "url": "https://fastapi.com/",
                                                "tags": ["python", "api"]})
    assert response1.status_code == 201
    response2 = client.post("/bookmarks", json={"title": "SQLAlchemy",
                                                "url": "https://sqlalchemy.com/",
                                                "tags": ["python", "database"]})
    assert response2.status_code == 201

    with SessionLocal() as db:
        tags = db.execute(select(Tag)).scalars().all()
        assert len(tags) == 3
        assert {tag.name for tag in tags} == {"python", "api", "database"}

        bookmark_fastapi = db.get(Bookmark, response1.json()["id"])
        assert {tag.name for tag in bookmark_fastapi.tags} == {"python", "api"}

        bookmark_sql = db.get(Bookmark, response2.json()["id"])
        assert {tag.name for tag in bookmark_sql.tags} == {"python", "database"}


@pytest.mark.parametrize("update_data", [
    {"tags": []},
    {"tags": ['API', 'api', ' API ']},
    {"tags": ['Python']},
    {"tags": ['fastapi', '    ', 'tests']}
])
def test_tags_partial_updates(reset_db, update_data):
    response_from_post = client.post('/bookmarks', json={'title': "FastAPI",
                                                         'url': "https://fastapi.com/",
                                                         'tags': ['python', 'dev']})

    old_data = response_from_post.json()
    bookmark_id = old_data['id']

    response = client.patch(f'/bookmarks/{bookmark_id}', json=update_data)
    assert response.status_code == 204

    expected_data = {tag.strip().lower() for tag in update_data['tags'] if tag.strip()}

    with SessionLocal() as db:
        db_bookmark = db.get(Bookmark, bookmark_id)
        db_tags = [tag_obj.name for tag_obj in db_bookmark.tags]

    assert expected_data == set(db_tags)
    assert db_bookmark.title == old_data["title"]
    assert db_bookmark.url == old_data["url"]


def test_delete_bookmark_removes_unused_tags(reset_db):
    response_from_first_post = client.post('/bookmarks', json={'title': 'FastAPI',
                                                               'url': "https://fastapi.com/",
                                                               'tags': ['api', 'python', 'dev']})
    assert response_from_first_post.status_code == 201
    response_from_second_post = client.post('/bookmarks', json={'title': 'SQLAlchemy',
                                                                'url': "https://sqlalchemy.com/",
                                                                'tags': ['python', 'database']})

    assert response_from_second_post.status_code == 201

    del_bookmark_id = response_from_first_post.json()["id"]

    response = client.delete(f'/bookmarks/{del_bookmark_id}')
    assert response.status_code == 204

    with SessionLocal() as db:
        assert db.get(Bookmark, del_bookmark_id) is None
        assert db.execute(select(Tag).where(Tag.name == 'dev')).scalar_one_or_none() is None
        assert db.execute(select(Tag).where(Tag.name == 'api')).scalar_one_or_none() is None

        db_tags = [tag_obj.name for tag_obj in db.execute(select(Tag)).scalars().all()]
        assert set(db_tags) == {'python', 'database'}


def test_get_tags_if_empty(reset_db):
    response = client.get('/tags')
    assert response.status_code == 200
    assert response.json() == []

    with SessionLocal() as db:
        assert db.execute(select(Tag)).scalars().all() == []


@pytest.fixture
def expected_tags_from_created_bookmarks(reset_db):
    bookmarks = [{'title': 'FastAPI', 'url': "https://fastapi.com/", 'tags': ['api', 'python', 'dev']},
                 {'title': 'SQLAlchemy', 'url': "https://sqlalchemy.com/", 'tags': ['python', 'database']},
                 {'title': 'Example', 'url': "https://example.com/", 'tags': []}]

    expected_tags = set()

    for bookmark in bookmarks:
        client.post("/bookmarks", json=bookmark)
        expected_tags.update(set(bookmark["tags"]))
    return expected_tags


def test_get_all_unique_tags_from_bookmarks(expected_tags_from_created_bookmarks):
    response = client.get('/tags')

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert all('name' in tag for tag in data)
    assert expected_tags_from_created_bookmarks == {tag["name"] for tag in data}


def test_get_boomkarks_by_not_existing_tag(reset_db):
    response = client.get('/tags/python/bookmarks')
    assert response.status_code == 200
    assert response.json() == []


@pytest.fixture
def expected_bookmarks_by_tags(reset_db):
    bookmarks = [{'title': 'FastAPI', 'url': "https://fastapi.com/", 'tags': ['api', 'python', 'dev']},
                 {'title': 'SQLAlchemy', 'url': "https://sqlalchemy.com/", 'tags': ['python', 'database']},
                 {'title': 'Example', 'url': "https://example.com/", 'tags': []}]

    expected_data_by_tags = defaultdict(set)

    for bookmark in bookmarks:
        response = client.post('/bookmarks', json=bookmark)
        assert response.status_code == 201
        for tag in bookmark["tags"]:
            expected_data_by_tags[tag].add((bookmark["title"], bookmark["url"]))

    return expected_data_by_tags


def test_get_boomkarks_by_existing_tags(expected_bookmarks_by_tags):

    for tag, expected_bookmarks in expected_bookmarks_by_tags.items():
        response = client.get(f'/tags/{tag}/bookmarks')
        assert response.status_code == 200

        data = response.json()
        assert len(data) == len(expected_bookmarks)

        actual_bookmarks = {(bookmark["title"], bookmark["url"]) for bookmark in data}
        assert expected_bookmarks == actual_bookmarks
