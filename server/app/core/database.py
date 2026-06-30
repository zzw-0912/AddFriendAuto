from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


SERVER_ROOT = Path(__file__).resolve().parents[2]


def _resolve_database_url(url: str) -> str:
    if not url.startswith("sqlite:///") or url.startswith("sqlite:////"):
        return url

    path_part = url.removeprefix("sqlite:///")
    if path_part == ":memory:":
        return url

    db_path = Path(path_part)
    if db_path.is_absolute():
        return url

    resolved = (SERVER_ROOT / db_path).resolve()
    return f"sqlite:///{resolved.as_posix()}"


database_url = _resolve_database_url(settings.database_url)


def _engine_kwargs(url: str) -> dict:
    if "sqlite" in url:
        return {"connect_args": {"check_same_thread": False}}

    kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    if url.startswith("mysql"):
        kwargs["connect_args"] = {"charset": "utf8mb4"}
    return kwargs


engine = create_engine(
    database_url,
    **_engine_kwargs(database_url),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
