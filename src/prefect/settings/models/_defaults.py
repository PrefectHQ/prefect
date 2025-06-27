from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr, ValidationInfo

if TYPE_CHECKING:
    from prefect.settings.models.root import Settings


def default_profiles_path(values: dict[str, Any]) -> Path:
    """Default profiles_path based on home directory."""
    home = values.get("home", Path("~/.prefect").expanduser())
    if not isinstance(home, Path):
        home = Path("~/.prefect").expanduser()
    return home / "profiles.toml"


def substitute_home_template(v: Any, info: ValidationInfo) -> Any:
    """Validator that substitutes $PREFECT_HOME in a path string if present."""
    home_path = info.data.get("home")

    path_str: str | None = None
    if isinstance(v, Path):
        return v
    elif isinstance(v, str):
        path_str = v
    elif v is None:
        return None
    else:
        return v

    if path_str and "$PREFECT_HOME" in path_str:
        if home_path and isinstance(home_path, Path):
            resolved_str = path_str.replace("$PREFECT_HOME", str(home_path))
            try:
                return Path(resolved_str)
            except Exception as e:
                raise ValueError(
                    f"Error creating path after substituting $PREFECT_HOME: {e}"
                ) from e
        else:
            raise ValueError(
                f'Cannot resolve $PREFECT_HOME in "{path_str}" because '
                f"PREFECT_HOME setting ({home_path!r}) is not a valid resolved path."
            )

    return path_str


def default_local_storage_path(values: dict[str, Any]) -> Path:
    """Default local_storage_path based on home directory."""
    home = values.get("home")
    if not isinstance(home, Path):
        home = Path("~/.prefect").expanduser()
    return home / "storage"


def default_memo_store_path(values: dict[str, Any]) -> Path:
    """Default memo_store_path based on home directory."""
    home = values.get("home")
    if not isinstance(home, Path):
        home = Path("~/.prefect").expanduser()
    return home / "memo_store.toml"


def default_logging_config_path(values: dict[str, Any]) -> Path:
    """Default logging_config_path based on home directory."""
    home = values.get("home")
    if not isinstance(home, Path):
        home = Path("~/.prefect").expanduser()
    return home / "logging.yml"


def default_database_connection_url(settings: "Settings") -> SecretStr:
    value: str = f"sqlite+aiosqlite:///{settings.home}/prefect.db"
    if settings.server.database.driver == "postgresql+asyncpg":
        required = [
            "host",
            "user",
            "name",
            "password",
        ]
        missing = [
            attr for attr in required if getattr(settings.server.database, attr) is None
        ]
        if missing:
            raise ValueError(
                f"Missing required database connection settings: {', '.join(missing)}"
            )

        from sqlalchemy import URL

        value = URL(
            drivername=settings.server.database.driver,
            host=settings.server.database.host,
            port=settings.server.database.port or 5432,
            username=settings.server.database.user,
            password=(
                settings.server.database.password.get_secret_value()
                if settings.server.database.password
                else None
            ),
            database=settings.server.database.name,
            query=[],  # type: ignore
        ).render_as_string(hide_password=False)

    elif settings.server.database.driver == "sqlite+aiosqlite":
        if settings.server.database.name:
            value = (
                f"{settings.server.database.driver}:///{settings.server.database.name}"
            )
        else:
            value = f"sqlite+aiosqlite:///{settings.home}/prefect.db"

    elif settings.server.database.driver:
        raise ValueError(
            f"Unsupported database driver: {settings.server.database.driver}"
        )
    return SecretStr(value)


def default_ui_url(settings: "Settings") -> str | None:
    value = settings.ui_url
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = settings.api.url

    if not api_url:
        return None
    assert ui_url is not None

    cloud_url = settings.cloud.api_url
    cloud_ui_url = settings.cloud.ui_url
    if api_url.startswith(cloud_url) and cloud_ui_url:
        ui_url = ui_url.replace(cloud_url, cloud_ui_url)

    if ui_url.endswith("/api"):
        # Handles open-source APIs
        ui_url = ui_url[:-4]

    # Handles Cloud APIs with content after `/api`
    ui_url = ui_url.replace("/api/", "/")

    # Update routing
    ui_url = ui_url.replace("/accounts/", "/account/")
    ui_url = ui_url.replace("/workspaces/", "/workspace/")

    return ui_url
