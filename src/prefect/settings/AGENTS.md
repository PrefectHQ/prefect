# Settings

This directory contains Prefect's settings system built on Pydantic settings.

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
