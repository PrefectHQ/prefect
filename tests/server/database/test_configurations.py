import asyncio
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
import sqlalchemy as sa

from prefect.server.database.configurations import AsyncPostgresConfiguration


def _add_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    params = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key
    ]
    params.append((key, value))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment)
    )


@pytest.mark.parametrize("stronger_default", ["repeatable read", "serializable"])
async def test_postgres_engine_enforces_read_committed(
    stronger_default: str,
    test_database_connection_url: str,
):
    """Prefect PostgreSQL engines override stronger database or role defaults and
    execute transactions at READ COMMITTED."""
    if not test_database_connection_url.startswith("postgresql+asyncpg"):
        pytest.skip("Test requires PostgreSQL")

    url = _add_query_param(
        test_database_connection_url,
        "default_transaction_isolation",
        stronger_default,
    )
    config = AsyncPostgresConfiguration(connection_url=url)
    engine = await config.engine()

    async def _check_isolation() -> tuple[str, str]:
        async with engine.begin() as conn:
            default_iso = (
                await conn.execute(sa.text("SHOW default_transaction_isolation"))
            ).scalar_one()
            txn_iso = (
                await conn.execute(sa.text("SHOW transaction_isolation"))
            ).scalar_one()
        return default_iso, txn_iso

    try:
        # Check two concurrently checked-out pooled connections.
        results = await asyncio.gather(_check_isolation(), _check_isolation())
        for default_iso, txn_iso in results:
            assert default_iso == stronger_default
            assert txn_iso == "read committed"
    finally:
        await engine.dispose()


class TestStatementCacheSizeZero:
    """0 is a meaningful value for both cache-size arguments, not an absent one.

    The settings that back them say so: statement_cache_size is documented as
    "required when using PgBouncer in transaction mode", and
    prepared_statement_cache_size as disabling the cache "when set to 0". Resolving
    either with `or` discards exactly that value.
    """

    @pytest.mark.parametrize(
        "field", ["statement_cache_size", "prepared_statement_cache_size"]
    )
    def test_zero_is_preserved(self, field: str) -> None:
        config = AsyncPostgresConfiguration(
            connection_url="postgresql+asyncpg://u:p@localhost/db", **{field: 0}
        )
        assert getattr(config, field) == 0, (
            f"{field}=0 was discarded; a caller disabling the cache silently gets "
            f"the default instead"
        )

    @pytest.mark.parametrize(
        "field", ["statement_cache_size", "prepared_statement_cache_size"]
    )
    def test_nonzero_is_preserved(self, field: str) -> None:
        config = AsyncPostgresConfiguration(
            connection_url="postgresql+asyncpg://u:p@localhost/db", **{field: 100}
        )
        assert getattr(config, field) == 100
