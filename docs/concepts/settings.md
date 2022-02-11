# Settings

Prefect's settings are [well-documented][prefect.settings] and type-validated. By modifying these settings, users can customize various aspects of the system.

Settings can be viewed from the CLI or the UI.

## Viewing settings from the CLI

The `prefect config view` command will display settings that override default values.

```bash
$ prefect config view
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG'
```

You may can show the sources of values with `--show-sources`:


```bash
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

You may also include default values with `--show-defaults`:

```bash
$ prefect config view --show-defaults
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG'
PREFECT_AGENT_PREFETCH_SECONDS='10'
PREFECT_AGENT_QUERY_INTERVAL='5.0'
PREFECT_DEBUG_MODE='False'
...
```

## Overriding defaults with environment variables

All settings can be modified via environment variables using the following syntax:
```
[PREFIX]_[SETTING]=value
```

- The `PREFIX` is a string that describes the fully-qualified name of the setting. All prefixes begin with `PREFECT_` and add additional words only to describe nested settings. For example, the prefix for `home` is just `PREFECT_`, because it is a top-level key in the `PrefectSettings` object. The prefix for `orion.api.port` is `PREFECT_ORION_API_`, indicating its nested position.
- The `SETTING` corresponds directly to the name of the prefect setting's key. Note that while keys are lowercase, we provide environment variables as uppercase by convention.

### Examples

Configuring a top-level setting:

```shell
# environment variable
export PREFECT_HOME="/path/to/home"
```
```python
# python
settings = prefect.settings.from_context()
settings.home  # PosixPath('/path/to/home')
```

Configuring a nested setting:

```shell
# environment variable
export PREFECT_ORION_API_PORT=4242
```
```python
# python
settings = prefect.settings.from_context()
settings.orion.api.port # 4242
```

## Persisting configuration values

Prefect allows you to persist settings instead of setting an environment variable each time you open a new shell.
Settings are persisted to profiles, which allow you to change settings quickly.

The default profile starts out empty:

```bash
$ prefect config get-profile
[default]
```

To persist a setting, use `prefect config set` and the same variable naming scheme as above:

```bash
$ prefect config set PREFECT_ORION_HOST="http://localhost:4200/api"
Set variable 'PREFECT_ORION_HOST' to 'http://localhost:4200/api'
Updated profile 'default'
```

This setting has been persisted to the profile:

```bash
$ prefect config get-profile
[default]
PREFECT_ORION_HOST = "http://localhost:4200/api"
```

And will be used by Prefect in the future:

```bash
$ prefect config view
PREFECT_PROFILE="default"
PREFECT_ORION_HOST='http://localhost:4200/api' (from profile)
```

See our [documentation on profiles](#profiles) for more details on working with profiles.

# Profiles

## Creating and removing profiles

Create a new profile with no settings:
```bash
$ prefect config create-profile test
Created profile 'test'.
```

Create a new profile with settings cloned from an existing profile:
```bash
$ prefect config create-profile foo --from default
Created profile 'foo' matching 'default'.
```

Rename a profile:
```bash
$ prefect config rename-profile foo bar
Renamed profile 'foo' to 'bar'.
```

Remove a profile:
```bash
$ prefect config rm-profile test
Removed profile 'test'.
```

Removing the default profile resets it:
```
$ prefect config rm-profile default
Reset profile 'default'.
```

## Change values in profiles

Set a value in the current profile:
```
$ prefect config set VAR=X
Set variable 'VAR' to 'X'
Updated profile 'default'
```

Set multiple values in the current profile:
```
$ prefect config set VAR2=Y VAR3=Z
Set variable 'VAR2' to 'Y'
Set variable 'VAR3' to 'Z'
Updated profile 'default'
```

Set a value in another profile:
```
$ prefect --profile "foo" config set VAR=Y
Set variable 'VAR' to 'Y'
Updated profile 'foo'
```

Unset values in the current profile:
```
$ prefect config unset VAR2 VAR3
Unset variable 'VAR2'
Unset variable 'VAR3'
Updated profile 'default'
```

## Inspecting profiles

List all profiles:
```
$ prefect config list-profiles
default
foo
```

View the current profile:
```
$ prefect config get-profile
[default]
VAR=X
```

View another profile:
```
$ prefect config get-profile foo
[foo]
VAR=Y
```

View multiple profiles:
```
$ prefect config get-profile default foo
[default]
VAR=X

[foo]
VAR=Y
```

View all profiles:
```
$ prefect config get-profiles
[default]
VAR = "X"

[foo]
VAR = "Y"
```

## Using profiles

The profile `"default"` is used by default. To use another profile, set the environment variable `PREFECT_PROFILE` to the name of the profile:

```
export PREFECT_PROFILE=foo
```

Or, specify the profile in the CLI command:

```
$ prefect --profile "foo" ...
```

Note that this option must come before the subcommand. For example, to list flow runs using the profile `"foo"`:

```
$ prefect --profile "foo" flow-run ls
```

You may use the `-p` flag as well:

```
$ prefect -p "foo" flow-run ls
```

You may also create an 'alias' to automatically use your profile:

```
$ alias prefect-foo="prefect --profile 'foo' "
$ prefect-foo config view  # uses our profile!
```

## Conflicts with environment variables

If setting the profile from the CLI with `--profile`, environment variables that conflict with settings in the profile will be ignored.

In all other cases, environment variables will take precedence over the value in the profile.

For example, a value set in a profile will be used by default:

```
$ prefect config set PREFECT_LOGGING_LEVEL="ERROR"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```

But, setting an environment variable will override the profile setting:

```
$ export PREFECT_LOGGING_LEVEL="DEBUG"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

Unless the profile is explicitly requested when using the CLI:

```
$ prefect --profile default config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```