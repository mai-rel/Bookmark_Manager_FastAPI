from fastapi import FastAPI, HTTPException, Response, Query, status
from sqlalchemy.exc import SQLAlchemyError
from app.schemas import BookmarkCreate,BookmarkUpdate, BookmarkResponse, TagResponse, BookmarkWithTagsResponse
from app.models import Bookmark, Tag
from app.db import SessionLocal, init_db, async_session
from typing import List
from datetime import timezone, datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload


app = FastAPI(title='Bookmark Manager API',
              description='Учебное приложение для изучения FastAPI',
              version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


#Bookmarks

@app.post("/bookmarks", status_code=status.HTTP_201_CREATED)
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

        tag_names = [tag_obj.name for tag_obj in db_bookmark.tags]

        response = BookmarkWithTagsResponse(id=db_bookmark.id, title=db_bookmark.title,
                                            url=db_bookmark.url, tags=tag_names, created_at=db_bookmark.created_at,
                                            updated_at=db_bookmark.updated_at)

        return response


@app.get("/bookmarks", response_model = List[BookmarkWithTagsResponse])
def get_bookmarks(query_title: str| None = None, query_tags: List[str] | None = Query(None),
                  sort: str| None = None, order: str = 'asc'):

    sortable_fields = {'title': Bookmark.title,
                       'created_at': Bookmark.created_at,
                       'updated_at': Bookmark.updated_at}

    with SessionLocal() as db:
        query = db.query(Bookmark)

        if query_title:
            query = query.filter(Bookmark.title.ilike(f'%{query_title}%'))

        if query_tags:
            query_tags = [tag.lower() for tag in query_tags]
            query = query.filter(Bookmark.tags.any(Tag.name.in_(query_tags)))

        if sort:
            field = sortable_fields.get(sort, None)
            if field is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong field for sorting")

            if order not in ('asc', 'desc'):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong sorting direction")

            if order == 'desc':
                query = query.order_by(field.desc(), Bookmark.id.desc())
            else:
                query = query.order_by(field, Bookmark.id)

        bookmarks = query.all()

        result = []
        for bookmark in bookmarks:
            tags_names = [tag_obj.name for tag_obj in bookmark.tags]
            response = BookmarkWithTagsResponse(id=bookmark.id, title=bookmark.title,
url=bookmark.url, tags=tags_names, created_at=bookmark.created_at, updated_at=bookmark.updated_at)
            result.append(response)

        return result


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
async def delete_bookmark(bookmark_id: int):
    async with async_session() as db:
        result = await db.execute(select(Bookmark).options(selectinload(Bookmark.tags)).where(Bookmark.id == bookmark_id))
        target_bookmark = result.scalar_one_or_none()
        if not target_bookmark:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

        bookmark_tags = target_bookmark.tags
        await db.delete(target_bookmark)
        await db.flush()

        for tag in bookmark_tags:
            result = await db.execute(select(Tag).where(Tag.name == tag.name, Tag.bookmarks.any() == False))
            del_tag = result.scalar_one_or_none()
            if del_tag:
                await db.delete(del_tag)
        await db.commit()
        return



#Tags

@app.get("/tags", response_model = List[TagResponse])
async def get_tags():
    async with async_session() as db:
        result = await db.execute(select(Tag))
        all_tags = result.scalars().all()
        return all_tags


@app.get("/tags/{tag_name}/bookmarks", response_model=List[BookmarkResponse])
async def get_bookmarks_by_tag(tag_name: str):
    async with async_session() as db:
        result = await db.execute(select(Tag).options(selectinload(Tag.bookmarks)).where(Tag.name == tag_name))
        tag_obj = result.scalar_one_or_none()
        if not tag_obj:
            return []

#         bookmarks_by_tag = [BookmarkResponse(id=bookmark_obj.id, title=bookmark_obj.title, url=
# bookmark_obj.url, created_at=bookmark_obj.created_at, updated_at=bookmark_obj.updated_at) for bookmark_obj in tag_obj.bookmarks]
#         return bookmarks_by_tag
        return tag_obj.bookmarks


