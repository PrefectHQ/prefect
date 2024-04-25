import pytest
from prefect_sqlalchemy.credentials import (
    AsyncDriver,
    ConnectionComponents,
    DatabaseCredentials,
    SyncDriver,
)
from sqlalchemy.engine import URL, Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from prefect import flow


@pytest.mark.parametrize(
    "url_param", ["driver", "username", "password", "database", "host", "port", "query"]
)
def test_sqlalchemy_credentials_post_init_url_param_conflict(url_param):
    @flow
    def test_flow():
        url_params = {url_param: url_param}
        if url_param == "query":
            url_params["query"] = {"query": "query"}
        with pytest.raises(
            ValueError, match="The `url` should not be provided alongside"
        ):
            DatabaseCredentials(
                url="postgresql+asyncpg://user:password@localhost:5432/database",
                **url_params,
            )

    test_flow()


@pytest.mark.parametrize("url_param", ["driver", "database"])
def test_sqlalchemy_credentials_post_init_url_param_missing(url_param):
    @flow
    def test_flow():
        url_params = {
            "driver": "driver",
            "database": "database",
        }
        url_params.pop(url_param)
        with pytest.raises(ValueError, match="If the `url` is not provided"):
            DatabaseCredentials(**url_params)

    test_flow()


@pytest.mark.parametrize(
    "driver", [AsyncDriver.POSTGRESQL_ASYNCPG, "postgresql+asyncpg"]
)
def test_sqlalchemy_credentials_get_engine_async(driver):
    @flow
    def test_flow():
        sqlalchemy_credentials = DatabaseCredentials(
            driver=driver,
            username="user",
            password="password",
            database="database",
            host="localhost",
            port=5432,
        )
        assert sqlalchemy_credentials._driver_is_async is True
        assert sqlalchemy_credentials.url is None

        expected_rendered_url = "postgresql+asyncpg://user:***@localhost:5432/database"
        assert repr(sqlalchemy_credentials.rendered_url) == expected_rendered_url
        assert isinstance(sqlalchemy_credentials.rendered_url, URL)

        engine = sqlalchemy_credentials.get_engine()
        assert engine.url.render_as_string() == expected_rendered_url
        assert isinstance(engine, AsyncEngine)

    test_flow()


@pytest.mark.parametrize(
    "driver", [SyncDriver.POSTGRESQL_PSYCOPG2, "postgresql+psycopg2"]
)
def test_sqlalchemy_credentials_get_engine_sync(driver):
    @flow
    def test_flow():
        sqlalchemy_credentials = DatabaseCredentials(
            driver=driver,
            username="user",
            password="password",
            database="database",
            host="localhost",
            port=5432,
        )
        assert sqlalchemy_credentials._driver_is_async is False
        assert sqlalchemy_credentials.url is None

        expected_rendered_url = "postgresql+psycopg2://user:***@localhost:5432/database"
        assert repr(sqlalchemy_credentials.rendered_url) == expected_rendered_url
        assert isinstance(sqlalchemy_credentials.rendered_url, URL)

        engine = sqlalchemy_credentials.get_engine()
        assert engine.url.render_as_string() == expected_rendered_url
        assert isinstance(engine, Engine)

    test_flow()


def test_sqlalchemy_credentials_get_engine_url():
    @flow
    def test_flow():
        url = "postgresql://username:password@account/database"
        sqlalchemy_credentials = DatabaseCredentials(url=url)
        assert sqlalchemy_credentials._driver_is_async is False
        assert sqlalchemy_credentials.url == url

        expected_rendered_url = "postgresql://username:***@account/database"
        assert repr(sqlalchemy_credentials.rendered_url) == expected_rendered_url
        assert isinstance(sqlalchemy_credentials.rendered_url, URL)

        engine = sqlalchemy_credentials.get_engine()
        assert engine.url.render_as_string() == expected_rendered_url
        assert isinstance(engine, Engine)

    test_flow()


def test_sqlalchemy_credentials_sqlite(tmp_path):
    @flow
    def test_flow():
        driver = SyncDriver.SQLITE_PYSQLITE
        database = str(tmp_path / "prefect.db")
        sqlalchemy_credentials = DatabaseCredentials(driver=driver, database=database)
        assert sqlalchemy_credentials._driver_is_async is False

        expected_rendered_url = f"sqlite+pysqlite:///{database}"
        assert repr(sqlalchemy_credentials.rendered_url) == expected_rendered_url
        assert isinstance(sqlalchemy_credentials.rendered_url, URL)

        engine = sqlalchemy_credentials.get_engine()
        assert engine.url.render_as_string() == expected_rendered_url
        assert isinstance(engine, Engine)

    test_flow()


def test_save_load_roundtrip():
    """
    This test was added because there was an issue saving rendered_url;
    sqlalchemy.engine.url.URL was not JSON serializable.
    """
    credentials = DatabaseCredentials(
        driver=AsyncDriver.POSTGRESQL_ASYNCPG,
        username="test-username",
        password="test-password",
        database="test-database",
        host="localhost",
        port="5678",
    )
    credentials.save("test-credentials", overwrite=True)
    loaded_credentials = credentials.load("test-credentials")
    assert loaded_credentials.driver == AsyncDriver.POSTGRESQL_ASYNCPG
    assert loaded_credentials.username == "test-username"
    assert loaded_credentials.password.get_secret_value() == "test-password"
    assert loaded_credentials.database == "test-database"
    assert loaded_credentials.host == "localhost"
    assert loaded_credentials.port == "5678"
    assert loaded_credentials.rendered_url == credentials.rendered_url


def test_sqlalchemy_connection_components_create_url_minimal():
    connection_components = ConnectionComponents(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2, database="my.db"
    )
    actual = connection_components.create_url()
    assert actual == make_url("postgresql+psycopg2:///my.db")


def test_sqlalchemy_connection_components_create_url_optional_params():
    connection_components = ConnectionComponents(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2,
        database="my.db",
        username="myusername",
        password="mypass",
        port=1234,
        host="localhost",
    )
    actual = connection_components.create_url()
    assert actual == make_url(
        "postgresql+psycopg2://myusername:mypass@localhost:1234/my.db"
    )
