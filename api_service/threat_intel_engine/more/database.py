"""Database models"""
# standard library
import logging
import os

# from multiprocessing import Lock
from threading import Lock

# third-party
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger('tcex')

Base = declarative_base()

# this lock is used to prevent multiple request from running when fork is launched
request_fork_lock = Lock()

sqlite_filepath = os.path.join(os.getenv('TC_DB_PATH'), 'app_store.db')


def get_engine():
    """Return engine."""
    return create_engine(
        f'sqlite:///{sqlite_filepath}',
        connect_args={
            'check_same_thread': False,
            'timeout': 5,
        },
        # echo='debug',
        # echo_pool='debug',
        poolclass=NullPool,
        # query_cache_size=0,
    )


def get_scoped_session(engine_):
    """Return scoped session."""
    return scoped_session(sessionmaker(bind=engine_))


engine = get_engine()
session = get_scoped_session(engine)
session.execute('PRAGMA foreign_keys = ON;')  # pylint: disable=no-member
session.commit()  # pylint: disable=no-member


def vacuum_db():
    """Vacuum the database."""
    try:
        session.execute('VACUUM')  # pylint: disable=no-member
        session.commit()  # pylint: disable=no-member
        logger.info('feature=initialize-db, event=vacuum-db')
    except Exception as e:
        logger.warning(f'feature=initialize-db, event=vacuum-db-failed, reason={e}')


def initialize_db():
    """Create all the database schemas."""
    Base.metadata.create_all(engine)

    # vacuum
    vacuum_db()
