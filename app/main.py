from fastapi import FastAPI, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from app.schemas import *
from app.models import *
from app.db import SessionLocal, init_db
from typing import List
from sqlalchemy import select, func, desc, distinct
from sqlalchemy.orm import selectinload


app = FastAPI(title='Bookmark Manager API',
              description='Учебное приложение для изучения FastAPI',
              version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


#Bookmarks

@app.post("/bookmarks", status_code=status.HTTP_201_CREATED, response_model=BookmarkWithTagsResponse)
def create_bookmark(bookmark: BookmarkCreate):
    with SessionLocal() as db:
        existing = db.execute(select(Bookmark).where(Bookmark.url == str(bookmark.url))).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bookmark with this URL already exists"
            )

        db_bookmark = Bookmark(title=bookmark.title, url=str(bookmark.url))
        tags_from_user = {tag.strip().lower() for tag in bookmark.tags if tag.strip()}
        tags_in_db = {tag_obj.name: tag_obj for tag_obj in db.query(Tag).filter(Tag.name.in_(tags_from_user))}
        final_tags = []

        for tag_name in tags_from_user:
            if not tag_name:
                continue
            if tag_name in tags_in_db:
                final_tags.append(tags_in_db[tag_name])
            else:
                new_tag = Tag(name=tag_name)
                db.add(new_tag)
                db.flush()
                final_tags.append(new_tag)

        db_bookmark.tags = final_tags
        db.add(db_bookmark)
        db.commit()
        db.refresh(db_bookmark)

        _ = db_bookmark.tags

        return db_bookmark



@app.get("/bookmarks", response_model=List[BookmarkWithTagsResponse])
def get_bookmarks(query_title: str | None = None, query_tags: List[str] | None = Query(None),
                  sort: str | None = None, order: str = 'asc'):

    sortable_fields = {'title': Bookmark.title,
                       'created_at': Bookmark.created_at,
                       'updated_at': Bookmark.updated_at}

    with SessionLocal() as db:
        statement = select(Bookmark).options(selectinload(Bookmark.tags))

        if query_title:
            statement = statement.where(Bookmark.title.ilike(f'%{query_title}%'))

        if query_tags:
            query_tags = [tag.lower() for tag in query_tags]
            statement = statement.where(Bookmark.tags.any(Tag.name.in_(query_tags)))

        if sort:
            field = sortable_fields.get(sort, None)
            if field is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong field for sorting")

            if order not in ('asc', 'desc'):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong sorting direction")

            if order == 'desc':
                statement = statement.order_by(field.desc(), Bookmark.id.desc())
            else:
                statement = statement.order_by(field, Bookmark.id)

        bookmarks = db.execute(statement).scalars().all()

        return bookmarks



@app.patch('/bookmarks/{bookmark_id}', status_code=status.HTTP_204_NO_CONTENT)
def update_bookmark(bookmark_id: int, updated_data: BookmarkUpdate):
    with SessionLocal() as db:
        db_bookmark = db.get(Bookmark, bookmark_id)
        if not db_bookmark:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

        if updated_data.title is not None:
            db_bookmark.title = updated_data.title
        if updated_data.url is not None:
            db_bookmark.url = str(updated_data.url)

        if updated_data.tags is not None:
            tags_from_user = {tag.strip().lower() for tag in updated_data.tags if tag.strip()}
            tags_in_db = {tag_obj.name: tag_obj for tag_obj in db.query(Tag).filter(Tag.name.in_(tags_from_user))}
            updated_tags = []
            for tag_name in tags_from_user:
                if tag_name in tags_in_db:
                    updated_tags.append(tags_in_db[tag_name])
                else:
                    new_tag = Tag(name=tag_name)
                    db.add(new_tag)
                    db.flush()
                    updated_tags.append(new_tag)

            db_bookmark.tags = updated_tags

        try:
            db.commit()
            return
        except SQLAlchemyError:
            db.rollback()
            print("Database update failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )


@app.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark_id: int):
    with SessionLocal() as db:
        target_bookmark = db.get(Bookmark, bookmark_id)
        if not target_bookmark:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

        bookmark_tags = target_bookmark.tags
        db.delete(target_bookmark)
        db.flush()

        for tag in bookmark_tags:
            if not tag.bookmarks:
                db.delete(tag)
        db.commit()
        return


#Tags

@app.get("/tags", response_model=List[TagResponse])
def get_tags():
    with SessionLocal() as db:
        all_tags = db.execute(select(Tag)).scalars().all()
        return all_tags


@app.get("/tags/{tag_name}/bookmarks", response_model=List[BookmarkResponse])
def get_bookmarks_by_tag(tag_name: str):
    with SessionLocal() as db:
        tag_obj = db.execute(select(Tag).where(Tag.name == tag_name)).scalar_one_or_none()
        if not tag_obj:
            return []

        bookmarks_by_tag = [BookmarkResponse(id=bookmark_obj.id,
                                             title=bookmark_obj.title,
                                             url=bookmark_obj.url,
                                             created_at=bookmark_obj.created_at,
                                             updated_at=bookmark_obj.updated_at) for bookmark_obj in tag_obj.bookmarks]
        return bookmarks_by_tag


# Other

@app.get('/bookmarks/stats', response_model=StatsResponse)
def get_bookmarks_stats():

    response = {'bookmarks': 0,
                'tags': 0,
                'bookmarks_without_tags': 0,
                'most_popular_tag': None,
                'earliest_bookmark': None,
                'latest_bookmark': None,
                'avg_tags_per_bookmark': 0}

    with SessionLocal() as db:
        bookmarks_count = db.execute(select(func.count(Bookmark.id))).scalar_one()
        response["bookmarks"] = bookmarks_count

        tags_count = db.execute(select(func.count(Tag.id))).scalar_one()
        response["tags"] = tags_count

        bookmarks_no_tags_count = db.execute(select(func.count(Bookmark.id)).where(~Bookmark.tags.any())).scalar_one()
        response["bookmarks_without_tags"] = bookmarks_no_tags_count

        if tags_count:
            top_tag_statement = (select(Tag.name)
                         .join(bookmark_tags)
                         .group_by(Tag.id, Tag.name)
                         .order_by(desc(func.count(bookmark_tags.c.bookmark_id)), Tag.name)
                         .limit(1))

            top_tag_name = db.execute(top_tag_statement).scalar_one()
            response['most_popular_tag'] = top_tag_name

            avg_tags_statement = (select(func.count(bookmark_tags.c.tag_id) /
                                          func.count(func.distinct(Bookmark.id)))
                                          .select_from(Bookmark)
                                          .outerjoin(bookmark_tags))

            avg_tags = db.execute(avg_tags_statement).scalar_one()
            response['avg_tags_per_bookmark'] = int(avg_tags)

        if bookmarks_count:
            bookmark_statement = select(Bookmark).options(selectinload(Bookmark.tags))
            earliest_bookmark = db.execute(bookmark_statement.order_by(Bookmark.created_at, Bookmark.id).limit(1)).scalar_one()
            latest_bookmark = db.execute(bookmark_statement.order_by(desc(Bookmark.created_at), desc(Bookmark.id)).limit(1)).scalar_one()

            response["earliest_bookmark"] = earliest_bookmark
            response["latest_bookmark"] = latest_bookmark

        return response
