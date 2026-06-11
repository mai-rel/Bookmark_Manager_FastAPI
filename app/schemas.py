from pydantic import BaseModel, HttpUrl
from typing import List


class BookmarkCreate(BaseModel):
    url: HttpUrl
    title: str
    tags: List[str]


class BookmarkUpdate(BaseModel):
    url: HttpUrl | None
    title: str | None
    tags: List[str] | None


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
    
