# Settings

This directory contains Prefect's settings system built on Pydantic settings.

## Structure

All settings are rooted in the `Settings` class in `models/root.py`, which composes top-level groups as nested Pydantic models. Each group lives in its own file (or subdirectory) under `models/`.

| Group | File | Scope |
|-------|------|-------|
| `api` | `models/api.py` | API connection settings (URL, key) |
| `cli` | `models/cli.py` | CLI behavior |
| `client` | `models/client.py` | HTTP client behavior (retries, CSRF, headers) |
| `cloud` | `models/cloud.py` | Prefect Cloud-specific config |
| `deployments` | `models/deployments.py` | Deployment defaults |
| `events` | `models/events.py` | Client-side event worker behavior (queue size) |
| `experiments` | `models/experiments.py` | Feature flags and experimental features |
| `flows` | `models/flows.py` | Flow behavior defaults |
| `internal` | `models/internal.py` | Internal machinery |
| `logging` | `models/logging.py` | Logging config (levels, API log shipping) |
| `plugins` | `models/plugins.py` | Plugin system config (`PREFECT_PLUGINS_*`); graduated from `experiments.plugins` |
| `results` | `models/results.py` | Result storage |
| `runner` | `models/runner.py` | Runner/serve behavior |
| `server` | `models/server/` | Server-side config (database, services, events, API, UI) — subdirectory with its own nested models |
| `tasks` | `models/tasks.py` | Task behavior (runner, scheduling) |
| `telemetry` | `models/telemetry.py` | Telemetry collection (resource metrics enable/interval) |
| `testing` | `models/testing.py` | Test mode flags |
| `worker` | `models/worker.py` | Worker behavior |

### Where to put a new setting

- **Server-side behavior** (database, orchestration services, server event processing) → `server.*` subtree
- **SDK-level domain concept** (flows, tasks, events, deployments) → top-level group matching the domain
- **HTTP client behavior** (retries, headers, CSRF) → `client`
- **If no existing group fits** → create a new top-level group: add a new file under `models/`, define the settings class, and wire it into `Settings` in `models/root.py`

## Adding New Settings

### Basic Pattern

New settings should use the simple `Field()` pattern without `validation_alias`:

```python
from pydantic import Field

class MyServiceSettings(ServicesBaseSetting):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "my_service")
    )

    my_setting: int = Field(
        default=100,
        gt=0,
        description="Description of what this setting controls.",
    )
```

The `build_settings_config()` function automatically generates the environment variable prefix from the path tuple. For the example above, the env var would be:
- `PREFECT_SERVER_SERVICES_MY_SERVICE_MY_SETTING`

### What NOT to do for new settings

Do **NOT** add `validation_alias` for new settings:

```python
# L Don't do this for new settings
my_setting: int = Field(
    default=100,
    validation_alias=AliasChoices(
        AliasPath("my_setting"),
        "prefect_server_services_my_service_my_setting",
    ),
)
```

### When validation_alias IS used

`validation_alias` exists only for **backward compatibility** with legacy environment variable names. You'll see it on older settings that needed to support both:
- Old format: `PREFECT_API_SERVICES_*`
- New format: `PREFECT_SERVER_SERVICES_*`

Example of a legacy setting with backward compatibility:

```python
# This exists for backward compatibility only
enabled: bool = Field(
    default=True,
    validation_alias=AliasChoices(
        AliasPath("enabled"),
        "prefect_server_services_scheduler_enabled",
        "prefect_api_services_scheduler_enabled",  # Legacy name
    ),
)
```

## Testing

When adding new settings, update `SUPPORTED_SETTINGS` in `tests/test_settings.py`:

```python
SUPPORTED_SETTINGS = {
    # ...
    "PREFECT_SERVER_SERVICES_MY_SERVICE_MY_SETTING": {"test_value": 50},
}
```

## Accessing Settings

```python
from prefect.settings.context import get_current_settings

settings = get_current_settings()
value = settings.server.services.my_service.my_setting
```
