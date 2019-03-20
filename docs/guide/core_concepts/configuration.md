# Configuration

Prefect's settings are stored in a configuration file called `config.toml`. In general, you should not edit this file directly to modify Prefect's settings. Instead, you should use [environment variables](#environment-variables) for temporary settings, or create a [user configuration file](#user-configuration) for permanent settings.

The configuration file is parsed when Prefect starts and available as `prefect.config`. To access any value, simply use dot-notation (for example, `prefect.config.tasks.defaults.checkpoint`).

## Environment variables

Any Prefect configuration key can be set by environment variable. In order to do so, prefix the variable with `PREFECT__` and use two underscores (`__`) to separate each part of the key.

For example, if you set `PREFECT__TASKS__DEFAULTS__MAX_RETRIES=4`, then `prefect.config.tasks.defaults.max_retries == 4`.

### Automatic type casting

Prefect will do its best to detect the type of your environment variable and cast it appropriately.

- `"True"` and `"true"` are converted to `True`
- `"False"` and `"false"` are converted to `False`
- strings that parse as integers are converted to integers
- strings that parse as floats are converted to floats
- all other values remain strings

## User configuration

In addition to environment variables, users can provide a custom configuration file. Any values in the custom configuration will be loaded *on top* of the default values, meaning the user configuration only needs to contain values you want to change.

Prefect will look for the user configuration at a location specified by `prefect.config.user_config_path`. By default, this is `$HOME/.prefect/config.toml`.

You can automatically generate a user configuration file at the default location by running `prefect make-user-config` from the CLI.


::: tip Changing the user config location
Since you shouldn't change the default settings directly, if you want to change the configuration location, set an environment variable `PREFECT__USER_CONFIG_PATH` appropriately.
:::

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
user = "${environments.${environment}}"

[environments]

    [environments.DEV]
        user = "test"

    [environments.PROD]
        user = "admin"
```

```python
assert prefect.config.environment == "PROD"
assert prefect.config.user == "admin"
```
