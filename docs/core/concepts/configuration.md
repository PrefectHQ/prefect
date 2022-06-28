# Configuration

Prefect's settings are stored in a configuration file called `config.toml`. In general, you should not edit this file directly to modify Prefect's settings. Instead, you should use [environment variables](#environment-variables) for temporary settings, or create a [user configuration file](#user-configuration) for permanent settings.

The configuration file is parsed when Prefect is first imported and is available as a live object in `prefect.config`. To access any value, use dot-notation (for example, `prefect.config.tasks.defaults.checkpoint`).

## Environment variables

Any lowercase Prefect configuration key can be set by environment variable. In order to do so, prefix the variable with `PREFECT__` and use two underscores (`__`) to separate each part of the key.

For example, if you set `PREFECT__TASKS__DEFAULTS__MAX_RETRIES=4`, then `prefect.config.tasks.defaults.max_retries == 4`.

!!! tip Interpolated keys are lowercase
Environment variables are always interpreted as lowercase configuration keys, _except_ whenever they are specifying local secrets. For example,

```
export PREFECT__LOGGING__LEVEL="INFO"
export PREFECT__CONTEXT__SECRETS__my_KEY="val"
```

will result in two configuration settings: one for `config.logging.level` and one for `config.context.secrets.my_KEY` (note that the casing on the latter is preserved).


### Automatic type casting

Prefect will do its best to detect the type of your environment variable and cast it appropriately.

- `"true"` (with any capitalization) is converted to `True`
- `"false"` (with any capitalization) is converted to `False`
- strings that parse as integers, floats, None, lists, dictionaries, etc. are all converted to their
respective Python type

## User configuration

In addition to environment variables, users can provide a custom configuration file. Any values in the custom configuration will be loaded _on top_ of the default values, but prior to interpolation, meaning the user configuration only needs to contain values you want to change.

By default, Prefect will look for a user configuration file at `$HOME/.prefect/config.toml`, but you can change that location by setting the environment variable `PREFECT__USER_CONFIG_PATH` appropriately. Please note the double-underscore (`__`) in the variable name; this ensures that it will be available at runtime as `prefect.config.user_config_path`.

### Configuration precedence

Configuration values set via environment variable have the highest priority; they will be respected even if a user configuration exists. User configuration files, in turn, have precedence over the default values.

## TOML

Prefect's configuration is written in [TOML](https://github.com/toml-lang/toml), a structured document that supports typed values and nesting.

### Extensions

Prefect extends standard TOML with two forms of variable interpolation.

#### Environment variable interpolation

Any string value that contains the name of an environment variable prefixed by "\$" will be replaced by the value of that environment variable when Prefect loads the configuration. For example, if `DIR=/foo` in your environment you could have the following key in your configuration:

```
path = "$DIR/file.txt"
```

In this case, loading `prefect.config.path == "/foo/file.txt"`

Environment variables are always interpreted as lowercase keys.

#### Configuration interpolation

If a string value refers to any other configuration key, enclosed in "\${" and "}", then the value of that key will be interpolated at runtime. This process is iterated a few times to resolve multiple references.

For example, this can be used to build values from other values:

```
[api]

host = "localhost"
port = "5432"
url = "https://${api.host}:${api.port}"
```

```python
assert prefect.config.api.url == "https://localhost:5432"
```

Or even to create complex switching logic based on the value of one variable:

```
environment = "prod"
user = "${environments.${environment}.user}"

[environments]

    [environments.dev]
        user = "test"

    [environments.prod]
        user = "admin"
```

```python
assert prefect.config.environment == "prod"
assert prefect.config.user == "admin"
```

#### Validation

Configs are recursively validated when first loaded. `ValueErrors` are raised for invalid config definitions. The checks include invalid keys; because `Config` objects have dictionary-like methods, it can create problems if any of their keys shadow one of their methods. For example, `"keys"` is an invalid key because `Config.keys()` is an important method.
