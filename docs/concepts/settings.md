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

## Commonly configured settings

This section describes some commonly configured settings for Prefect installations. See [Configuring settings](#configuring-settings) for details on setting and unsetting configuration values.

### PREFECT_API_URL

The `PREFECT_API_URL` value specifies the API endpoint of your Prefect Cloud workspace or Prefect server instance.

For example, using a local Prefect server instance.
```bash
PREFECT_API_URL="http://127.0.0.1:4200/api"
```

Using Prefect Cloud:

```bash
PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
```

!!! tip "`PREFECT_API_URL` setting for agents"
    When using [agents and work pools](/concepts/work-pools/) that can create flow runs for deployments in remote environments,  [`PREFECT_API_URL`](/concepts/settings/) must be set for the environment in which your agent is running. 

    If you want the agent to communicate with Prefect Cloud or a Prefect server instance from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.


!!! tip "Running the Prefect UI behind a reverse proxy"
    When using a reverse proxy (such as [Nginx](https://nginx.org) or [Traefik](https://traefik.io)) to proxy traffic to a locally-hosted Prefect UI instance, the Prefect server also needs to be configured to know how to connect to the API. The  [`PREFECT_UI_API_URL`](prefect/settings/#PREFECT_UI_API_URL)  should be set to the external proxy URL (e.g. if your external URL is https://prefect-server.example.com/ then set `PREFECT_UI_API_URL=https://prefect-server.example.com/api` for the Prefect server process).  You can also accomplish this by setting [`PREFECT_API_URL`](/concepts/settings/#prefect.settings.PREFECT_API_URL) to the API URL, as this setting is used as a fallback if `PREFECT_UI_API_URL` is not set.


### PREFECT_API_KEY

The `PREFECT_API_KEY` value specifies the [API key](/ui/cloud-api-keys/#create-an-api-key) used to authenticate with your Prefect Cloud workspace.

```bash
PREFECT_API_KEY="[API-KEY]"
```

### PREFECT_HOME

The `PREFECT_HOME` value specifies the local Prefect directory for configuration files, profiles, and the location of the default [Prefect SQLite database](/concepts/database/).

```bash
PREFECT_HOME='~/.prefect'
```

### PREFECT_LOCAL_STORAGE_PATH

The `PREFECT_LOCAL_STORAGE_PATH` value specifies the default location of local storage for flow runs.

```bash
PREFECT_LOCAL_STORAGE_PATH='${PREFECT_HOME}/storage'
```
### Database settings

Prefect provides several settings for configuring the [Prefect database](/concepts/database/).

```bash
PREFECT_API_DATABASE_CONNECTION_URL='sqlite+aiosqlite:///${PREFECT_HOME}/prefect.db'
PREFECT_API_DATABASE_ECHO='False'
PREFECT_API_DATABASE_MIGRATE_ON_START='True'
PREFECT_API_DATABASE_PASSWORD='None'
```

### Logging settings

Prefect provides several settings for configuring [logging level and loggers](/concepts/logs/).

```bash
PREFECT_LOGGING_EXTRA_LOGGERS=''
PREFECT_LOGGING_LEVEL='INFO'
```

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
PREFECT_PROFILE='default'
PREFECT_AGENT_PREFETCH_SECONDS='10' (from defaults)
PREFECT_AGENT_QUERY_INTERVAL='5.0' (from defaults)
PREFECT_API_KEY='None' (from defaults)
PREFECT_API_REQUEST_TIMEOUT='30.0' (from defaults)
PREFECT_API_URL='None' (from defaults)
...
```

### Setting and clearing values

The `prefect config set` command lets you change the value of a default setting.

A commonly used example is setting the `PREFECT_API_URL`, which you may need to change when interacting with different Prefect server instances or Prefect Cloud.

```bash
# use a local Prefect server
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"

# use Prefect Cloud
prefect config set PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
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
export PREFECT_SERVER_API_PORT=4242
```
```python
# python
prefect.settings.PREFECT_SERVER_API_PORT.value()  # 4242
```

## Configuration profiles

Prefect allows you to persist settings instead of setting an environment variable each time you open a new shell.
Settings are persisted to profiles, which allow you to change settings quickly.

The `prefect profile` CLI commands enable you to create, review, and manage profiles.

| Command | Description |
| --- | --- |
| create | Create a new profile. |
| delete | Delete the given profile. |
| inspect | Display settings from a given profile; defaults to active. |
| ls | List profile names. |
| rename | Change the name of a profile. |
| use | Switch the active profile. |

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

View all settings for a profile:

```bash
$ prefect profile inspect cloud
PREFECT_API_URL='https://api.prefect.cloud/api/accounts/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx
x/workspaces/xxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
PREFECT_API_KEY='xxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'          
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
