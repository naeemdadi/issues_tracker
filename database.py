from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.echo,
)

SessionLocal = sessionmaker(bind=engine)

def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
