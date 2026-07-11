from pydantic import BaseModel, HttpUrl, constr
from typing import List


class BookmarkCreate(BaseModel):
    url: HttpUrl
    title: constr(min_length=1, strip_whitespace=True)
    tags: set[str] = set()


class BookmarkUpdate(BaseModel):
    url: HttpUrl | None = None
    title: constr(min_length=1, strip_whitespace=True) | None = None
    tags: set[str] | None = None


class BookmarkResponse(BaseModel):
    url: HttpUrl
    title: str
    tags: List[str]

    class Config:
        from_attributes = True



class TagResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True


class BookmarkNoTagsResponse(BaseModel):
    title: str
    url: HttpUrl

    class Config:
        from_attributes = True
    
