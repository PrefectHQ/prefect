import sqlalchemy as sa
from sqlalchemy import select

from prefect.orion.models import orm


def create_flow(session: sa.orm.Session, name: str) -> orm.Flow:
    try:
        nested = session.begin_nested()
        flow = orm.Flow(name=name)
        session.add(flow)
        session.flush()
        return flow
    except:
        nested.rollback()
        stmt = session.execute(select(orm.Flow).filter_by(name=name))
        return stmt.scalar()
