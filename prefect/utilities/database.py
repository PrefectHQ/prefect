import contextlib
from sqlalchemy import create_engine, orm

from prefect import config

engine = None
_sessionmaker = None
session = None


def connect(**engine_args):
    global engine
    global _sessionmaker
    global session

    engine = create_engine(config.get('db', 'connection_url'))
    _sessionmaker = orm.sessionmaker(
        autocommit=False, autoflush=False, bind=engine)
    session = orm.scoped_session(_sessionmaker)

    # initialize in-memory databases
    if str(engine.url) == 'sqlite://':
        initialize()


def initialize():
    """
    Initialize the Prefect database:
        - create tables
        - create indices / constraints
        - create relationships
    """
    # make sure models have been created
    from prefect import models

    models.Base.metadata.create_all(engine)
    with transaction() as s:

        # ensure namespaces exist
        s.add(models.Namespace(name='prefect'))
        s.add(models.Namespace(name=config.get('flows', 'default_namespace')))


@contextlib.contextmanager
def transaction(commit=True, new=False):
    """
    Context manager that provides a session object and issues a rollback
    on any error.

    Args:
        commit (bool): if True, the transaction is committed when the context
            manager is exited. Otherwise, the session is flushed but not
            committed.
        new (bool): if True, creates a new session and closes it with the
            context manager exits. Otherwise, resuses the main scoped_session.
    """
    if new:
        sess = _sessionmaker()
    else:
        sess = session
    try:
        yield sess
        if commit:
            sess.commit()
        else:
            sess.flush()
    except Exception:
        sess.rollback()
        raise
    finally:
        if new:
            sess.close()
