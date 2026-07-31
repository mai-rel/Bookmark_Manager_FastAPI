from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.db import Base, engine, SessionLocal
from pydantic import HttpUrl
from collections import Counter


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_stats_empty_db(reset_db):
    empty_db_stats = {'bookmarks': 0,
                      'tags': 0,
                      'bookmarks_without_tags': 0,
                      'most_popular_tag': None,
                      'earliest_bookmark': None,
                      'latest_bookmark': None,
                      'avg_tags_per_bookmark': 0}

    response = client.get('/bookmarks/stats')
    assert response.status_code == 200
    assert response.json() == empty_db_stats


def test_stats_one_bookmark_no_tags(reset_db):
    response_from_post = client.post('/bookmarks', json={'title': 'FastAPI', 'url': "https://fastapi.com/"})
    assert response_from_post.status_code == 201

    response = client.get('/bookmarks/stats')
    assert response.status_code == 200

    actual_stats = response.json()

    assert actual_stats["bookmarks"] == 1
    assert actual_stats["tags"] == 0
    assert actual_stats['bookmarks_without_tags'] == 1
    assert actual_stats['most_popular_tag'] is None
    assert actual_stats['earliest_bookmark'] is not None
    assert actual_stats['latest_bookmark'] is not None
    assert actual_stats['avg_tags_per_bookmark'] == 0


def test_total_bookmarks_and_total_tags(reset_db):

    response_fastapi = client.post('/bookmarks', json={'title': 'FastAPI',
                                                       'url': "https://fastapi.com/",
                                                       "tags": ["api", "python", "dev"]})
    assert response_fastapi.status_code == 201

    response_sql = client.post('/bookmarks', json={'title': 'SQLAlchemy',
                                                         'url': "https://sqlalchemy.com/",
                                                         'tags': ['python', 'database']})
    assert response_sql.status_code == 201

    response = client.get('bookmarks/stats')
    assert response.status_code == 200

    actual_stats = response.json()
    assert actual_stats["bookmarks"] == 2
    assert actual_stats["tags"] == 4


def normalize(bookmark):
    return {"title": bookmark["title"],
            "url": str(HttpUrl(bookmark["url"])),
            "tags": set(bookmark["tags"])}


@pytest.fixture
def created_bookmarks(reset_db):
    bookmarks = [{'title': 'FastAPI', 'url': "https://fastapi.com/", 'tags': ['example', 'api', 'python']},
                 {'title': 'SQLAlchemy', 'url': "https://sqlalchemy.com/", 'tags': ['python', 'example']},
                 {'title': 'Example', 'url': "https://example.com/", 'tags': ['example']}]

    for bookmark in bookmarks:
        client.post("/bookmarks", json=bookmark)
    return [normalize(bookmark) for bookmark in bookmarks]



def test_get_earliest_and_latest_bookmark(created_bookmarks):
    response = client.get('/bookmarks/stats')

    assert response.status_code == 200

    data = response.json()
    fields = {'title', 'id', 'created_at', 'updated_at', 'url'}

    earliest_bookmark = data['earliest_bookmark']
    assert fields <= earliest_bookmark.keys()
    assert earliest_bookmark['url'] == created_bookmarks[0]['url']
    assert earliest_bookmark["title"] == created_bookmarks[0]["title"]

    latest_bookmark = data["latest_bookmark"]
    assert fields <= latest_bookmark.keys()
    assert latest_bookmark['url'] == created_bookmarks[-1]['url']
    assert latest_bookmark["title"] == created_bookmarks[-1]["title"]



def test_get_most_popular_tag(created_bookmarks):
    response = client.get('/bookmarks/stats')
    assert response.status_code == 200

    tags = Counter()
    for bookmark in created_bookmarks:
        for tag_name in bookmark["tags"]:
            tags[tag_name] += 1

    expected_tag = sorted(tags.items(), key=lambda x: (-x[1], x[0]))[0][0]
    assert response.json()['most_popular_tag'] == expected_tag


def test_avg_tags_per_bookmark(created_bookmarks):
    response = client.get('/bookmarks/stats')
    assert response.status_code == 200

    actual_avg_tags = response.json()["avg_tags_per_bookmark"]

    bookmarks_count = len(created_bookmarks)
    tags_count = sum([len(bookmark["tags"]) for bookmark in created_bookmarks])
    expected_avg_tags = tags_count / bookmarks_count

    assert actual_avg_tags == pytest.approx(expected_avg_tags)




