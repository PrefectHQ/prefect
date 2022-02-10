# Settings

Prefect's settings are [well-documented][prefect.settings] and type-validated. By modifying these settings, users can customize various aspects of the system.

Settings can be viewed from the CLI or the UI.

## Viewing settings from the CLI

The `prefect diagnostics` command will display settings that override default values.

```bash
$ prefect diagnostics
Profile: default
Settings:
  PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

You may also include default values with `--show-defaults`:

```bash
$ prefect diagnostics --show-defaults
Profile: default
Settings:
  PREFECT_LOGGING_LEVEL='DEBUG' (from env)
  PREFECT_AGENT_PREFETCH_SECONDS='10' (from defaults)
  PREFECT_AGENT_QUERY_INTERVAL='5.0' (from defaults)
  PREFECT_DEBUG_MODE='False' (from defaults)
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

## Overriding defaults with profiles

Profiles allow you to persist settings instead of setting an environment variable each time you open a new shell.

The default profile starts out empty:

```bash
$ prefect profile inspect
[default]
```

To persist a setting, use `prefect profile set` and the same variable naming scheme as above:

```bash
$ prefect profile set PREFECT_ORION_HOST="http://localhost:4200/api"
Set variable 'PREFECT_ORION_HOST' to 'http://localhost:4200/api'
Updated profile 'default'
```

This setting has been persisted now:

```bash
$ prefect profile inspect
[default]
PREFECT_ORION_HOST = "http://localhost:4200/api"
```

And will be used by Prefect in the future:

```bash
$ prefect diagnostics
Profile: default
Settings:
  PREFECT_ORION_HOST='http://localhost:4200/api' (from profile)
```

See our [documentation on profiles](#profiles) for more details on working with profiles.

# Profiles

## Creating and removing profiles

Create a new profile with no settings:
```bash
$ prefect profile create test
Created profile 'test'.
```

Create a new profile with settings cloned from an existing profile:
```bash
$ prefect profile create foo --from default
Created profile 'foo' matching 'default'.
```

Remove a profile:
```bash
$ prefect profile rm test
Removed profile 'test'.
```

Removing the default profile resets it:
```
$ prefect profile rm default
Reset profile 'default'.
```


## Change values in profiles

Set a value in the current profile:
```
$ prefect profile set VAR=X
Set variable 'VAR' to 'X'
Updated profile 'default'
```

Set multiple values in the current profile:
```
$ prefect profile set VAR2=Y VAR3=Z
Set variable 'VAR2' to 'Y'
Set variable 'VAR3' to 'Z'
Updated profile 'default'
```

Set a value in another profile:
```
$ prefect --profile "foo" profile set VAR=Y
Set variable 'VAR' to 'Y'
Updated profile 'foo'
```

Unset values in the current profile:
```
$ prefect profile unset VAR2 VAR3
Unset variable 'VAR2'
Unset variable 'VAR3'
Updated profile 'default'
```

## Examing profiles

List all profiles:
```
$ prefect profile ls
default
foo
```

Inspect the current profile:
```
$ prefect profile inspect
[default]
VAR=X
```

Inspect another profile:
```
$ prefect profile inspect foo
[foo]
VAR=Y
```

Inspect all profiles:
```
$ prefect profile inspect --all
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

## Conflicts with environment variables

If setting the profile from the CLI with `--profile`, environment variables that conflict with settings in the profile will be ignored.

In all other cases, environment variables will take precedence over the value in the profile.

For example, a value set in a profile will be used by default:

```
$ prefect profile set PREFECT_LOGGING_LEVEL="ERROR"
$ prefect diagnostics
Profile: default
Settings:
  PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```

But, setting an environment variable will override the profile setting:

```
$ export PREFECT_LOGGING_LEVEL="DEBUG"
$ prefect diagnostics
Profile: default
Settings:
  PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

Unless the profile is explicitly requested when using the CLI:

```
$ prefect --profile default diagnostics
Profile: default
Settings:
  PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```