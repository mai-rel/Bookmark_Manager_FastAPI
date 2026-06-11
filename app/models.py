from sqlalchemy import Column, Integer, String, Table, ForeignKey
from app.db import Base
from sqlalchemy.orm import relationship


bookmark_tags = Table(
    "bookmark_tags",
    Base.metadata,
    Column("bookmark_id", ForeignKey("bookmarks.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    url = Column(String)

    tags = relationship(
        "Tag",
        secondary=bookmark_tags,
        back_populates="bookmarks"
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    bookmarks = relationship("Bookmark", secondary=bookmark_tags, 
back_populates = 'tags')


