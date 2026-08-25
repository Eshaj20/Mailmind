from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# The database engine is created using the SQLAlchemy create_engine function, which connects to the database specified in the application's settings. The SessionLocal class is a session factory that provides a new SQLAlchemy Session object for each request, with autoflush and autocommit disabled to allow for explicit transaction management. The Base class serves as the declarative base for defining ORM models in the application.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
