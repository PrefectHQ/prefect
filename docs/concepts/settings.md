---
description: Prefect settings let you customize your workflow environment, including working with remote Prefect servers and Prefect Cloud.
tags:
    - configuration
    - settings
    - environment variables
    - profiles
---

# Settings

Prefect's settings are [well-documented][prefect.settings.Settings] and type-validated. By modifying these settings, users can customize various aspects of the system.

Settings can be viewed from the CLI or the UI.

Settings have keys that match environment variables that can be used to override the settings in a profile.

Prefect provides the ability to organize settings as [profiles](#configuration-profiles) and apply the settings persisted in a profile. When you change profiles, all of the settings configured in the profile are applied. You can apply profiles to individual commands or set a profile for your environment.

## Configuring settings

The `prefect config` CLI commands enable you to view, set, and unset settings.

| Command | Description |
| --- | --- |
| set | Change the value for a setting. |
| unset | Restore the default value for a setting. |
| view | Display the current settings. |

### Viewing settings from the CLI

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

### Setting and clearing values

The `prefect config set` command lets you change the value of a default setting.

A commonly used example is setting the `PREFECT_API_URL`, which you may need to change when interacting with different Orion API server instances or Prefect Cloud.

```bash
# use a local Orion API server
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

# use Prefect Cloud
prefect config set PREFECT_API_URL=http://beta.prefect.io/api
```

If you want to configure a setting to use its default value, use the `prefect config unset` command.

```bash
prefect config unset PREFECT_API_URL
```

### Overriding defaults with environment variables

All settings have keys that match the environment variable that can be used to override them.

For example, configuring the home directory:

```shell
# environment variable
export PREFECT_HOME="/path/to/home"
```
```python
# python
import prefect.settings
prefect.settings.PREFECT_HOME.value()  # PosixPath('/path/to/home')
```

Configuring the server's port:

```shell
# environment variable
export PREFECT_ORION_API_PORT=4242
```
```python
# python
prefect.settings.PREFECT_ORION_API_PORT.value()  # 4242
```

## Configuration profiles

Prefect allows you to persist settings instead of setting an environment variable each time you open a new shell.
Settings are persisted to profiles, which allow you to change settings quickly.

The `prefect profile` CLI commands enable you to create, review, and manage profiles.

| Command | Description |
| --- | --- |
| create | Create a new profile. |
| use | Switch the active profile. |
| delete | Delete the given profile. |
| inspect | Display settings from a given profile; defaults to active. |
| ls | List profile names. |
| rename | Change the name of a profile. |

The default profile starts out empty:

```bash
$ prefect profile get
[default]
```

If you configured settings for a profile, `prefect profile inspect` displays those settings:

```bash
$ prefect profile inspect
PREFECT_PROFILE = "default"
PREFECT_API_KEY = "pnu_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
PREFECT_API_URL = "http://127.0.0.1:4200/api"
```

You can pass the name of a profile to view its settings:

```bash
$ prefect profile create test
$ prefect profile inspect test
PREFECT_PROFILE="test"
```

### Creating and removing profiles

Create a new profile with no settings:

```bash
$ prefect profile create test
Created profile 'test' at /Users/terry/.prefect/profiles.toml.
```

Create a new profile `foo` with settings cloned from an existing `default` profile:

```bash
$ prefect profile create foo --from default
Created profile 'cloud' matching 'default' at /Users/terry/.prefect/profiles.toml.
```

Rename a profile:

```bash
$ prefect profile rename temp test
Renamed profile 'temp' to 'test'.
```

Remove a profile:

```bash
$ prefect profile delete test
Removed profile 'test'.
```

Removing the default profile resets it:

```bash
$ prefect profile delete default
Reset profile 'default'.
```

### Change values in profiles

Set a value in the current profile:

```bash
$ prefect config set VAR=X
Set variable 'VAR' to 'X'
Updated profile 'default'
```

Set multiple values in the current profile:

```bash
$ prefect config set VAR2=Y VAR3=Z
Set variable 'VAR2' to 'Y'
Set variable 'VAR3' to 'Z'
Updated profile 'default'
```

You can set a value in another profile by passing the `--profile NAME` option to a CLI command:

```bash
$ prefect --profile "foo" config set VAR=Y
Set variable 'VAR' to 'Y'
Updated profile 'foo'
```

Unset values in the current profile to restore the defaults:

```bash
$ prefect config unset VAR2 VAR3
Unset variable 'VAR2'
Unset variable 'VAR3'
Updated profile 'default'
```

### Inspecting profiles

See a list of available profiles:

```bash
$ prefect profile ls
* default
cloud
test
local
```

View the current profile:

```bash
$ prefect profile get
[default]
VAR=X
```

View another profile:

```bash
$ prefect profile get foo
[foo]
VAR=Y
```

View multiple profiles:

```bash
$ prefect profile get default foo
[default]
VAR=X

[foo]
VAR=Y
```

View all settings for a profile, including defaults:

```bash
$ prefect profile inspect --show-defaults
PREFECT_PROFILE='default'
PREFECT_API_URL=''
PREFECT_AGENT_PREFETCH_SECONDS='10'
PREFECT_AGENT_QUERY_INTERVAL='5.0'
PREFECT_API_KEY='None'
PREFECT_API_REQUEST_TIMEOUT='30.0'
PREFECT_API_URL='None'
PREFECT_DEBUG_MODE='False'
PREFECT_HOME='/Users/terry/.prefect'
PREFECT_LOGGING_EXTRA_LOGGERS=''
PREFECT_LOGGING_LEVEL='INFO'
PREFECT_LOGGING_ORION_BATCH_INTERVAL='2.0'
PREFECT_LOGGING_ORION_BATCH_SIZE='4000000'
PREFECT_LOGGING_ORION_ENABLED='True'
PREFECT_LOGGING_ORION_MAX_LOG_SIZE='1000000'
PREFECT_LOGGING_SERVER_LEVEL='WARNING'
PREFECT_LOGGING_SETTINGS_PATH='${PREFECT_HOME}/logging.yml'
PREFECT_ORION_ANALYTICS_ENABLED='True'
PREFECT_ORION_API_DEFAULT_LIMIT='200'
PREFECT_ORION_API_HOST='127.0.0.1'
PREFECT_ORION_API_PORT='4200'
PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT='5.0'
PREFECT_ORION_DATABASE_CONNECTION_URL='sqlite+aiosqlite:////${PREFECT_HOME}/orion.db'
PREFECT_ORION_DATABASE_ECHO='False'
PREFECT_ORION_DATABASE_MIGRATE_ON_START='True'
PREFECT_ORION_DATABASE_TIMEOUT='1.0'
PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS='0:00:05'
PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED='True'
PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS='5.0'
PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE='100'
PREFECT_ORION_SERVICES_SCHEDULER_ENABLED='True'
PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE='500'
PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS='60.0'
PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS='100'
PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME='100 days, 0:00:00'
PREFECT_ORION_UI_ENABLED='True'
PREFECT_PROFILES_PATH='${PREFECT_HOME}/profiles.toml'
PREFECT_TEST_MODE='False'
```

### Using profiles

The profile `default` is used by default. There are several methods to switch to another profile.

The recommended method is to use the `prefect profile use` command with the name of the profile:

```bash
$ prefect profile use foo
Profile 'test' now active.
```

Alternatively, you may set the environment variable `PREFECT_PROFILE` to the name of the profile:

```bash
$ export PREFECT_PROFILE=foo
```

Or, specify the profile in the CLI command for one-time usage:

```bash
$ prefect --profile "foo" ...
```

Note that this option must come before the subcommand. For example, to list flow runs using the profile `foo`:

```bash
$ prefect --profile "foo" flow-run ls
```

You may use the `-p` flag as well:

```bash
$ prefect -p "foo" flow-run ls
```

You may also create an 'alias' to automatically use your profile:

```bash
$ alias prefect-foo="prefect --profile 'foo' "
# uses our profile!
$ prefect-foo config view  
```

## Conflicts with environment variables

If setting the profile from the CLI with `--profile`, environment variables that conflict with settings in the profile will be ignored.

In all other cases, environment variables will take precedence over the value in the profile.

For example, a value set in a profile will be used by default:

```bash
$ prefect config set PREFECT_LOGGING_LEVEL="ERROR"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```

But, setting an environment variable will override the profile setting:

```bash
$ export PREFECT_LOGGING_LEVEL="DEBUG"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

Unless the profile is explicitly requested when using the CLI:

```bash
$ prefect --profile default config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```

## Profile files

Profiles are persisted to the `PREFECT_PROFILES_PATH`, which can be changed with an environment variable.

By default, it is stored in your `PREFECT_HOME` directory:

```
$ prefect config view --show-defaults | grep PROFILES_PATH
PREFECT_PROFILES_PATH='~/.prefect/profiles.toml'
```

The [TOML](https://toml.io/en/) format is used to store profile data.
