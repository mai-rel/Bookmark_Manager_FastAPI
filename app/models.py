from sqlalchemy import Column, Table, ForeignKey, DateTime, func
from app.db import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tags: Mapped[list["Tag"]] = relationship(
        secondary=bookmark_tags,
        back_populates="bookmarks",
    )

    user_id: Mapped[int| None] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="bookmarks")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)

    bookmarks: Mapped[list["Bookmark"]] = relationship(
        secondary=bookmark_tags,
        back_populates="tags",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bookmarks: Mapped[list["Bookmark"]] = relationship(back_populates="user")
