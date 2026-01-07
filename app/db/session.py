import os
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from typing import Generator

load_dotenv()  # loads .env if present

# Prefer DATABASE_URL if set (e.g. postgres://user:pass@host:port/dbname)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_ENGINE = os.getenv("DB_ENGINE", "sqlite")
    if DB_ENGINE == "sqlite":
        # local sqlite file
        db_file = os.getenv("SQLITE_FILE", "lab_scheduler.db")
        DATABASE_URL = f"sqlite:///{db_file}"
    else:
        # Build postgres-like url
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "postgres")
        DATABASE_URL = f"{DB_ENGINE}://{user}:{password}@{host}:{port}/{name}"
        
print(f"Using database at {DATABASE_URL}")

# Engine options
DB_ECHO = os.getenv("DB_ECHO", "false").lower() in ("1", "true", "yes")
POOL_SIZE = int(os.getenv("POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW", "20"))

# For SQLite we keep NullPool to avoid 'sqlite unable to use pool' issues
connect_args = {}
engine_kwargs = {"echo": DB_ECHO}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, poolclass=NullPool, **engine_kwargs)
else:
    # PostgreSQL connection settings for Neon and other cloud databases
    connect_args = {
        "connect_timeout": 10,
        "options": "-c timezone=utc"
    }
    
    engine_kwargs.update({
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_pre_ping": True,  # Test connections before using them
        "pool_recycle": 300,     # Recycle connections after 5 minutes
        "connect_args": connect_args
    })
    
    engine = create_engine(DATABASE_URL, **engine_kwargs)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes.
    Usage: `with get_session() as session:` or in FastAPI dependency injection.
    """
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """
    Convenience function to create tables from SQLModel metadata.
    Not used in production if Alembic is used; useful for local dev tests.
    """
    # Import all models explicitly to ensure they're registered
    from app.db.models import (Organization, AuthUser, Department, Staff,
                               Shift, Skill, StaffSkill, ShiftAssignment,
                               LeaveRequest)

    # Create all tables at once with proper metadata ordering
    # This ensures SQLAlchemy can resolve all dependencies properly
    SQLModel.metadata.create_all(engine, checkfirst=True)
