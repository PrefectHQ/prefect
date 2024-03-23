---
description: Prefect settings let you customize your workflow environment, including working with Prefect server and Prefect Cloud.
tags:
    - configuration
    - settings
    - environment variables
    - profiles
title: Profiles and Configuration
search:
  boost: 2
---

# Profiles & Configuration

Prefect's local settings are [documented][prefect.settings.Settings] and type-validated. 

By modifying the default settings, you can customize various aspects of the system. 
You can override a setting with an environment variable or by updating the setting in a Prefect [profile](#configuration-profiles).

Prefect profiles are persisted groups of settings on your local machine. A single profile is always active.

Initially, a default profile named `default` is active and contains no settings overrides.

All currently active settings can be viewed from the command line by running the following command:

<div class="terminal">
```bash
prefect config view --show-defaults
```
</div>

When you switch to a different profile, all of the settings configured in the newly activated profile are applied. 

## Commonly configured settings

This section describes some commonly configured settings. 
See [Configuring settings](#configuring-settings) for details on setting and unsetting configuration values.

### PREFECT_API_KEY

The `PREFECT_API_KEY` value specifies the [API key](/ui/cloud-api-keys/#create-an-api-key) used to authenticate with Prefect Cloud.

```bash
PREFECT_API_KEY="[API-KEY]"
```

Generally, you will set the `PREFECT_API_URL` and `PREFECT_API_KEY` for your active profile by running `prefect cloud login`. 
If you're curious, read more about [managing API keys](/cloud/users/api-keys/). 

### PREFECT_API_URL

The `PREFECT_API_URL` value specifies the API endpoint of your Prefect Cloud workspace or a self-hosted Prefect server instance.

For example, if using Prefect Cloud:

<div class="terminal">
```bash
PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
```
</div>

You can view your Account ID and Workspace ID in your browser URL when at a Prefect Cloud workspace page. 
For example: <https://app.prefect.cloud/account/abc-my-account-id-is-here/workspaces/123-my-workspace-id-is-here>.

If using a local Prefect server instance, set your API URL like this:

<div class="terminal">
```bash
PREFECT_API_URL="http://127.0.0.1:4200/api"
```
</div>

!!! tip "`PREFECT_API_URL` setting for workers"

    If using a [worker](/concepts/work-pools/) (agent and block-based deployments are legacy) that can create flow runs for deployments in remote environments,  [`PREFECT_API_URL`](/concepts/settings/) must be set for the environment in which your worker is running.

    If you want the worker to communicate with Prefect Cloud or a Prefect server instance from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.

!!! tip "Running the Prefect UI behind a reverse proxy"

    When using a reverse proxy (such as [Nginx](https://nginx.org) or [Traefik](https://traefik.io)) to proxy traffic to a locally-hosted Prefect UI instance, the Prefect server instance also needs to be configured to know how to connect to the API. 
    The [`PREFECT_UI_API_URL`](../../api-ref/prefect/settings/#PREFECT_UI_API_URL) should be set to the external proxy URL (e.g. if your external URL is <https://prefect-server.example.com/> then set `PREFECT_UI_API_URL=https://prefect-server.example.com/api` for the Prefect server process). 
    You can also accomplish this by setting [`PREFECT_API_URL`](/concepts/settings/#prefect.settings.PREFECT_API_URL) to the API URL, as this setting is used as a fallback if `PREFECT_UI_API_URL` is not set.

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

### CSRF Protection Settings

If using a local Prefect server instance, you can configure CSRF protection settings.

`PREFECT_SERVER_CSRF_PROTECTION_ENABLED`
- Activates CSRF protection on the server, requiring valid CSRF tokens for applicable requests. Recommended for production to prevent CSRF attacks. Defaults to False.

```bash
PREFECT_SERVER_CSRF_PROTECTION_ENABLED=True
```

`PREFECT_SERVER_CSRF_TOKEN_EXPIRATION`
- Sets the expiration duration for server-issued CSRF tokens, influencing how often tokens need to be refreshed. The default is 1 hour.

```bash
PREFECT_SERVER_CSRF_TOKEN_EXPIRATION='3600'  # 1 hour in seconds
```

By default clients expect that CSRF protection is enabled on the server. If you are running a server without CSRF protection, you can disable CSRF support in the client.

`PREFECT_CLIENT_CSRF_SUPPORT_ENABLED`
- Enables or disables CSRF token handling in the Prefect client. When enabled, the client manages CSRF tokens for state-changing API requests. Defaults to True.

```bash
PREFECT_CLIENT_CSRF_SUPPORT_ENABLED=True
```



### Database settings

If running a self-hosted Prefect server instance, there are several database configuration settings you can read about [here](/host/).

### Logging settings

Prefect provides several logging configuration settings that you can read about in the [logging docs](/concepts/logs/).

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

You can show the sources of values with `--show-sources`:

```bash
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```

You can also include default values with `--show-defaults`:

```bash
$ prefect config view --show-defaults
PREFECT_PROFILE='default'
PREFECT_AGENT_PREFETCH_SECONDS='10' (from defaults)
PREFECT_AGENT_QUERY_INTERVAL='5.0' (from defaults)
PREFECT_API_KEY='None' (from defaults)
PREFECT_API_REQUEST_TIMEOUT='60.0' (from defaults)
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

<div class="terminal">
```bash
# environment variable
export PREFECT_HOME="/path/to/home"
```
</div>

```python
# python
import prefect.settings
prefect.settings.PREFECT_HOME.value()  # PosixPath('/path/to/home')
```

Configuring the a server instance's port:

<div class="terminal">
```bash
# environment variable
export PREFECT_SERVER_API_PORT=4242
```
</div>

```python
# python
prefect.settings.PREFECT_SERVER_API_PORT.value()  # 4242
```

## Configuration profiles

Prefect allows you to persist settings instead of setting an environment variable each time you open a new shell.
Settings are persisted to profiles, which allow you to move between groups of settings quickly.

The `prefect profile` CLI commands enable you to create, review, and manage profiles.

| Command | Description |
| --- | --- |
| create | Create a new profile. |
| delete | Delete the given profile. |
| inspect | Display settings from a given profile; defaults to active. |
| ls | List profile names. |
| rename | Change the name of a profile. |
| use | Switch the active profile. |

If you configured settings for a profile, `prefect profile inspect` displays those settings:

<div class="terminal">
```bash
$ prefect profile inspect
PREFECT_PROFILE = "default"
PREFECT_API_KEY = "pnu_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
PREFECT_API_URL = "http://127.0.0.1:4200/api"
```
</div>

You can pass the name of a profile to view its settings:

<div class="terminal">
```bash
$ prefect profile create test
$ prefect profile inspect test
PREFECT_PROFILE="test"
```
</div>

### Creating and removing profiles

Create a new profile with no settings:

<div class="terminal">
```bash
$ prefect profile create test
Created profile 'test' at /Users/terry/.prefect/profiles.toml.
```
</div>

Create a new profile `foo` with settings cloned from an existing `default` profile:

<div class="terminal">
```bash
$ prefect profile create foo --from default
Created profile 'cloud' matching 'default' at /Users/terry/.prefect/profiles.toml.
```
</div>

Rename a profile:

<div class="terminal">
```bash
$ prefect profile rename temp test
Renamed profile 'temp' to 'test'.
```
</div>

Remove a profile:

<div class="terminal">
```bash
$ prefect profile delete test
Removed profile 'test'.
```
</div>

Removing the default profile resets it:

<div class="terminal">
```bash
$ prefect profile delete default
Reset profile 'default'.
```
</div>

### Change values in profiles

Set a value in the current profile:

<div class="terminal">
```bash
$ prefect config set VAR=X
Set variable 'VAR' to 'X'
Updated profile 'default'
```
</div>

Set multiple values in the current profile:

<div class="terminal">
```bash
$ prefect config set VAR2=Y VAR3=Z
Set variable 'VAR2' to 'Y'
Set variable 'VAR3' to 'Z'
Updated profile 'default'
```
</div>

You can set a value in another profile by passing the `--profile NAME` option to a CLI command:

<div class="terminal">
```bash
$ prefect --profile "foo" config set VAR=Y
Set variable 'VAR' to 'Y'
Updated profile 'foo'
```
</div>

Unset values in the current profile to restore the defaults:

<div class="terminal">
```bash
$ prefect config unset VAR2 VAR3
Unset variable 'VAR2'
Unset variable 'VAR3'
Updated profile 'default'
```
</div>

### Inspecting profiles

See a list of available profiles:

<div class="terminal">
```bash
$ prefect profile ls
* default
cloud
test
local
```
</div>

View all settings for a profile:

<div class="terminal">
```bash
$ prefect profile inspect cloud
PREFECT_API_URL='https://api.prefect.cloud/api/accounts/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx
x/workspaces/xxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
PREFECT_API_KEY='xxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'          
```
</div>

### Using profiles

The profile named `default` is used by default. There are several methods to switch to another profile.

The recommended method is to use the `prefect profile use` command with the name of the profile:

<div class="terminal">
```bash
$ prefect profile use foo
Profile 'test' now active.
```
</div>

Alternatively, you can set the environment variable `PREFECT_PROFILE` to the name of the profile:

<div class="terminal">
```bash
export PREFECT_PROFILE=foo
```
</div>

Or, specify the profile in the CLI command for one-time usage:

<div class="terminal">
```bash
prefect --profile "foo" ...
```
</div>

Note that this option must come before the subcommand. For example, to list flow runs using the profile `foo`:

<div class="terminal">
```bash
prefect --profile "foo" flow-run ls
```
</div>

You may use the `-p` flag as well:

<div class="terminal">
```bash
prefect -p "foo" flow-run ls
```
</div>

You may also create an 'alias' to automatically use your profile:

<div class="terminal">
```bash
$ alias prefect-foo="prefect --profile 'foo' "
# uses our profile!
$ prefect-foo config view  
```
</div>

## Conflicts with environment variables

If setting the profile from the CLI with `--profile`, environment variables that conflict with settings in the profile will be ignored.

In all other cases, environment variables will take precedence over the value in the profile.

For example, a value set in a profile will be used by default:

<div class="terminal">
```bash
$ prefect config set PREFECT_LOGGING_LEVEL="ERROR"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```
</div>

But, setting an environment variable will override the profile setting:

<div class="terminal">
```bash
$ export PREFECT_LOGGING_LEVEL="DEBUG"
$ prefect config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='DEBUG' (from env)
```
</div>

Unless the profile is explicitly requested when using the CLI:

<div class="terminal">
```bash
$ prefect --profile default config view --show-sources
PREFECT_PROFILE="default"
PREFECT_LOGGING_LEVEL='ERROR' (from profile)
```
</div>

## Profile files

Profiles are persisted to the file location specified by `PREFECT_PROFILES_PATH`. 
The default location is a `profiles.toml` file in the `PREFECT_HOME` directory:

<div class="terminal">
```bash
$ prefect config view --show-defaults
...
PREFECT_PROFILES_PATH='${PREFECT_HOME}/profiles.toml'
...
```
</div>

The [TOML](https://toml.io/en/) format is used to store profile data.
