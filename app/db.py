from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, DeclarativeBase

DATABASE_URL = "sqlite:///./bookmarks.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, 
bind=engine)

class Base(DeclarativeBase):
    pass


def init_db():
    Base.metadata.create_all(bind=engine)
