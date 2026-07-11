from pydantic import BaseModel, HttpUrl, constr, ConfigDict
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
    id: int
    title: str
    url: HttpUrl

    model_config = ConfigDict(from_attributes=True)


class BookmarkWithTagsResponse(BookmarkResponse):
    tags: List[str]


class TagResponse(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)



    
