from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.models import User, Bookmark
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import Base, engine
import pytest
from app.main import app


client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_create_user_in_db_success(reset_db):
    user1_data = {'username': 'Mairel', 'email': 'mairel.veys@mail.ru'}

    with SessionLocal() as db:
        db_user = User(username=user1_data['username'],
                       email=user1_data['email'],
                       hashed_password='fake_password')
        db.add(db_user)
        db.commit()

        db_user = db.execute(select(User)).scalar_one()
        assert db_user.username == 'Mairel'
        assert db_user.email == 'mairel.veys@mail.ru'


@pytest.fixture
def create_user_in_db(reset_db):
    user_data = {'username': 'Mairel', 'email': 'mairel.veys@mail.ru'}
    with SessionLocal() as db:
        user = User(username=user_data['username'],
                       email=user_data['email'],
                       hashed_password='fake_password')
        db.add(user)
        db.commit()



@pytest.mark.parametrize("user_data", [
    {'username': 'Mairel', 'email': 'new@mail.ru'},
    {'username': 'New', 'email': 'mairel.veys@mail.ru'}])
def test_cannot_create_user_with_existing_name_or_email(create_user_in_db, user_data):
    with SessionLocal() as db:
        user = User(username=user_data['username'],
                    email=user_data['email'],
                    hashed_password='fake_password')
        db.add(user)

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()



def test_user_bookmarks_relationship(create_user_in_db):
    with SessionLocal() as db:
        db_user = db.execute(select(User)).scalar_one()
        user_id = db_user.id

        bookmark = Bookmark(title="FastAPI",
                            user_id=user_id,
                            url="https://fastapi.com/")

        db.add(bookmark)
        db.commit()
        db.refresh(db_user)

        user_bookmarks = db_user.bookmarks
        assert len(user_bookmarks) == 1

        data = user_bookmarks[0]
        assert (data.title, data.url) == ("FastAPI", "https://fastapi.com/")

        db_bookmark = db.execute(select(Bookmark)).scalar_one()
        bookmark_user = db_bookmark.user
        assert isinstance(bookmark_user, User)
        assert (bookmark_user.username, bookmark_user.email) == ("Mairel", 'mairel.veys@mail.ru')















