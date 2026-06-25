from fastapi import FastAPI, HTTPException, Response, Query, status
from app.schemas import BookmarkCreate,BookmarkUpdate, BookmarkResponse, TagResponse,BookmarkNoTagsResponse
from app.models import Bookmark, Tag
from app.db import SessionLocal, init_db
from typing import List

app = FastAPI()

@app.on_event("startup")
def startup():
    init_db()


@app.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: int):
    with SessionLocal() as db:
        target_bookmark = db.query(Bookmark).filter(Bookmark.id == bookmark_id).first()
        if not target_bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        db.delete(target_bookmark)
        db.commit()
        return Response(status_code=204)


@app.get("/bookmarks", response_model = List[ BookmarkResponse])
def get_bookmarks(query_title: str| None = None, query_tags: List[str] | None = Query(None)):
    with SessionLocal() as db:

        query = db.query(Bookmark)

        if query_title:
            query = query.filter(Bookmark.title.ilike(f'%{query_title}%'))

        if query_tags:
            query = query.filter(Bookmark.tags.any(Tag.name.in_(query_tags)))

        bookmarks = query.all()

        result = []
        for bookmark in bookmarks:
            tags_names = [tag_obj.name for tag_obj in bookmark.tags]
            response = BookmarkResponse(title=bookmark.title, 
url=bookmark.url, tags=tags_names)
            result.append(response)

        return result


@app.post("/bookmarks", status_code=status.HTTP_201_CREATED)
def create_bookmark(bookmark: BookmarkCreate):
    with SessionLocal() as db:
        existing = db.query(Bookmark).filter(Bookmark.url == str(bookmark.url)).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bookmark with this URL already exists"
            )

        db_bookmark = Bookmark(title=bookmark.title, url=str(bookmark.url))
        tags_from_user = {tag.strip().lower() for tag in bookmark.tags}
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

        response = BookmarkResponse(title=db_bookmark.title,
                                    url=db_bookmark.url, tags=tag_names)

        headers = {"Location": f"/bookmarks/{db_bookmark.id}"}

        return response, headers




@app.patch('/bookmarks/{bookmark_id}')
def update_bookmark(bookmark_id: int, updated_data: BookmarkUpdate):
    with SessionLocal() as db:
        db_bookmark = db.query(Bookmark).filter(Bookmark.id==bookmark_id).first()
        if not db_bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        if updated_data.title is not None:
            db_bookmark.title = updated_data.title
        if updated_data.url is not None:
            db_bookmark.url = str(updated_data.url)

        if updated_data.tags is not None:
            tags_in_db = {tag_obj.name: tag_obj for tag_obj in db.query(Tag).all()}
            updated_tags = []
            for tag_name in updated_data.tags:
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
            return {'message': "Successfully updated"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Server error")


@app.get("/tags", response_model = List[TagResponse])
def get_tags():
    with SessionLocal() as db:
        all_tags = db.query(Tag).all()
        return all_tags


@app.get("/tags/{tag_name}/bookmarks", response_model = 
List[BookmarkNoTagsResponse])
def get_bookmarks_by_tag(tag_name: str):
    with SessionLocal() as db:
        tag_obj = db.query(Tag).filter(Tag.name==tag_name).first()
        if not tag_obj:
            return []

        bookmarks_by_tag = [BookmarkNoTagsResponse(title=bookmark_obj.title, url= 
bookmark_obj.url) 
for bookmark_obj in  tag_obj.bookmarks]
        return bookmarks_by_tag
