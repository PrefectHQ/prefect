"""Initial MySQL-compatible schema.

Revision ID: 3d1b2a5f0f1a
Revises:
Create Date: 2026-05-11 16:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.elements import UnaryExpression

from prefect.server.database.orm_models import Base

# revision identifiers, used by Alembic.
revision = "3d1b2a5f0f1a"
down_revision = None
branch_labels = None
depends_on = None

# OceanBase / MySQL require prefix lengths for BTREE indexes on TEXT/BLOB columns, e.g. `(col(255))`.
# SQLAlchemy: Index(..., mysql_length={...}). UniqueConstraint does not support mysql_length, so those
# columns stay VARCHAR(255) instead.
MYSQL_TEXT_INDEX_PREFIX_LEN = 255


def _mysql_type_upper(column: sa.Column, dialect: sa.Dialect) -> str:
    return column.type.compile(dialect=dialect).upper()


def _is_text_or_blob(mysql_type: str) -> bool:
    return any(token in mysql_type for token in ("TEXT", "BLOB"))


def _index_references_json(table: sa.Table, index: sa.Index, dialect: sa.Dialect) -> bool:
    for expr in index.expressions:
        name = getattr(expr, "name", None)
        if not name:
            continue
        column = table.c.get(name)
        if column is None:
            continue
        if "JSON" in _mysql_type_upper(column, dialect):
            return True
    return False


def _index_expr_base_column(expr: object) -> sa.Column | None:
    if isinstance(expr, sa.Column):
        return expr
    if isinstance(expr, UnaryExpression) and isinstance(expr.element, sa.Column):
        return expr.element
    return None


def _index_references_timestamp(table: sa.Table, index: sa.Index) -> bool:
    """True if any column in this index has a TIMESTAMP/DATETIME type.

    Unique indexes on timestamp columns cannot be reliably enforced at second
    precision: MySQL truncates sub-second values, causing false duplicates
    when two state transitions occur within the same second.
    """
    _TIMESTAMP_TYPES = (sa.DateTime, sa.TIMESTAMP)
    for expr in index.expressions:
        base = _index_expr_base_column(expr)
        if base is None:
            continue
        col = table.c.get(base.key)
        if col is None:
            continue
        col_type = col.type
        # unwrap TypeDecorator to its impl
        impl = getattr(col_type, "impl", col_type)
        if isinstance(impl, type):
            impl = impl()
        if isinstance(col_type, _TIMESTAMP_TYPES) or isinstance(impl, _TIMESTAMP_TYPES):
            return True
    return False


def _mysql_requires_simple_column_index(index: sa.Index) -> bool:
    """True if this index should be created on MySQL/OceanBase as-is.

    Supports plain columns and ``column ASC`` / ``column DESC`` only. Dialects reject
    arbitrary expressions (e.g. ``coalesce(a, b) DESC``) with syntax errors.
    """
    for expr in index.expressions:
        if isinstance(expr, sa.Column):
            continue
        if isinstance(expr, UnaryExpression) and isinstance(expr.element, sa.Column):
            continue
        return False
    return bool(index.expressions)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        unique_column_names: set[str] = set()
        for constraint in copied.constraints:
            if isinstance(constraint, sa.UniqueConstraint):
                for column in constraint.columns:
                    unique_column_names.add(column.name)

        for column in copied.columns:
            mysql_type = _mysql_type_upper(column, dialect)
            if isinstance(column.type, sa.Interval) and column.server_default is not None:
                # Interval -> DATETIME on MySQL; DEFAULT '0' is rejected (1067). Zero duration is the
                # Unix epoch, matching MYSQL_EPOCH / interval arithmetic in server utilities.
                column.server_default = sa.text("'1970-01-01 00:00:00'")
            if column.server_default is not None and any(
                token in mysql_type for token in ("JSON", "TEXT", "BLOB")
            ):
                # OceanBase(MySQL mode) does not allow defaults on JSON/TEXT/BLOB columns.
                column.server_default = None
            if column.name in unique_column_names and _is_text_or_blob(mysql_type):
                # No mysql_length on UniqueConstraint; use a bounded string type instead.
                column.type = sa.String(length=MYSQL_TEXT_INDEX_PREFIX_LEN)

        indexes_snapshot = list(copied.indexes)
        for index in indexes_snapshot:
            if index not in copied.indexes:
                continue
            # Postgres GIN indexes on JSON become plain BTREE under MySQL, which OceanBase rejects
            # (e.g. error 3152: JSON column cannot be used in key specification).
            if _index_references_json(copied, index, dialect):
                copied.indexes.discard(index)
                continue
            if not _mysql_requires_simple_column_index(index):
                copied.indexes.discard(index)
                continue
            # Unique indexes on (run_id, timestamp) cannot be enforced at second
            # precision: two state transitions within the same second produce
            # identical truncated timestamps and collide on the constraint.
            # Demote these to plain (non-unique) indexes for MySQL.
            if index.unique and _index_references_timestamp(copied, index):
                index.unique = False

            length_by_name: dict[str, int] = {}
            for expr in index.expressions:
                base = _index_expr_base_column(expr)
                if base is None:
                    continue
                col = copied.c.get(base.key)
                if col is None:
                    continue
                if _is_text_or_blob(_mysql_type_upper(col, dialect)):
                    length_by_name[col.name] = MYSQL_TEXT_INDEX_PREFIX_LEN

            if length_by_name:
                copied.indexes.discard(index)
                # mysql_length + UnaryExpression (.asc/.desc) breaks MySQL DDL compilation
                # (dialect expects each indexed column to have .name). Use plain columns;
                # index sort order may differ from Postgres for these TEXT/BLOB prefix indexes.
                index_parts: list[sa.Column] = []
                for expr in index.expressions:
                    base = _index_expr_base_column(expr)
                    if base is None:
                        raise NotImplementedError(
                            "MySQL initial migration only supports simple column indexes; "
                            f"got unexpected expression in index {index.name!r} on {copied.name!r}"
                        )
                    index_parts.append(copied.c[base.key])

                mysql_length: int | dict[str, int]
                keyed_parts = [
                    b
                    for expr in index.expressions
                    if (b := _index_expr_base_column(expr)) is not None
                ]
                if len(length_by_name) == 1 and len(keyed_parts) == 1:
                    mysql_length = next(iter(length_by_name.values()))
                else:
                    mysql_length = {
                        part.name: length_by_name[part.name]
                        for part in keyed_parts
                        if part.name in length_by_name
                    }

                sa.Index(
                    index.name,
                    *index_parts,
                    unique=index.unique,
                    mysql_length=mysql_length,
                )

    metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=bind)
    metadata.drop_all(bind=bind)
