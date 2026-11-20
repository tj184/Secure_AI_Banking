
import os

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./securebank.db"
)


# =====================================================
# ENGINE
# =====================================================

engine_options = {
    "pool_pre_ping": True,
}

if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False
    }


engine = create_engine(
    DATABASE_URL,
    **engine_options
)


# =====================================================
# SQLITE FOREIGN KEY SUPPORT
# =====================================================

if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):

        cursor = dbapi_connection.cursor()

        cursor.execute("PRAGMA foreign_keys=ON")

        cursor.close()


# =====================================================
# BASE MODEL
# =====================================================

Base = declarative_base()


# =====================================================
# SESSION FACTORY
# =====================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


# =====================================================
# DATABASE DEPENDENCY
# =====================================================

def get_db():
    """
    Provides a database session.

    Useful for FastAPI dependencies and other
    functions that need database access.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =====================================================
# TRANSACTIONAL SESSION
# =====================================================

@contextmanager
def session_scope():
    """
    Provides a database session with automatic
    commit and rollback handling.
    """

    db = SessionLocal()

    try:
        yield db

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# =====================================================
# INITIALIZE DATABASE
# =====================================================

def init_db():
    """
    Creates all registered database tables.
    """

    # Import models to register them with Base.
    import database.models

    Base.metadata.create_all(bind=engine)

    print("SecureBank database initialized successfully.")


# =====================================================
# DATABASE HEALTH CHECK
# =====================================================

def check_db_connection():

    from sqlalchemy import text

    try:

        with engine.connect() as connection:

            connection.execute(text("SELECT 1"))

        return True

    except Exception as error:

        print(f"Database connection failed: {error}")

        return False
