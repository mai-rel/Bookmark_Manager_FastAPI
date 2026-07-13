from sqlalchemy import Column, Table, ForeignKey
from app.db import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column


bookmark_tags = Table(
    "bookmark_tags",
    Base.metadata,
    Column("bookmark_id", ForeignKey("bookmarks.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str]
    url: Mapped[str]

    tags: Mapped[list["Tag"]] = relationship(
        secondary=bookmark_tags,
        back_populates="bookmarks",
    )



class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] =  mapped_column(primary_key=True, index=True)
    name: Mapped[str] =  mapped_column(unique=True, index=True)

    bookmarks: Mapped[list["Bookmark"]] = relationship(
        secondary=bookmark_tags,
        back_populates="tags",
    )


