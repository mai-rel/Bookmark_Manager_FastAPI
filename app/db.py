from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


DATABASE_URL = "sqlite:///./bookmarks.db"
ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./bookmarks.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
async_engine = create_async_engine(ASYNC_DATABASE_URL)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, 
bind=engine)
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    Base.metadata.create_all(bind=engine)
