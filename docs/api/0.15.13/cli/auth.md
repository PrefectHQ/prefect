---
sidebarDepth: 2
editLink: false
---
# auth
---
### login
```
Login to Prefect Cloud

  Create an API key in the UI then login with it here:

      $ prefect auth login -k YOUR-KEY

  You will be switched to the default tenant associated with the key. After
  login, your available tenants can be seen with `prefect auth list-tenants`
  and you can change the default tenant on this machine using `prefect auth
  switch-tenants`.

  The given key will be stored on disk for later access. Prefect will default
  to using this key for all interaction with the API but frequently overrides
  can be passed to individual commands or functions. To remove your key from
  disk, see `prefect auth logout`.

  This command has backwards compatibility support for API tokens, which are a
  deprecated form of authentication with Prefect Cloud

Options:
  -k, --key TEXT    A Prefect Cloud API key.
  -t, --token TEXT  A Prefect Cloud API token. DEPRECATED.
  --help            Show this message and exit.
```

### logout
```
Log out of Prefect Cloud

  This will remove your cached authentication from disk.

Options:
  -t, --token  Log out from the API token based authentication, ignoring API
               keys
  --help       Show this message and exit.
```

### list-tenants
```
List available tenants

Options:
  --help  Show this message and exit.
```

### switch-tenants
```
Switch active tenant

Options:
    --id, -i    TEXT    A Prefect Cloud tenant id
    --slug, -s  TEXT    A Prefect Cloud tenant slug
```

### create-key
```
Create a Prefect Cloud API key for authentication with your current user

Options:
  -n, --name TEXT    A name to associate with the key  [required]
  -e, --expire TEXT  A optional dateutil parsable time to at. If not given,
                     the key will never expire.
  -q, --quiet        If set, only display the created key.
  --help             Show this message and exit.
```

### list-keys
```
List Prefect Cloud API keys

  If you are a tenant admin, this should list all service account keys as well
  as keys you have created.

Options:
  --help  Show this message and exit.
```

### revoke-key
```
Revoke a Prefect Cloud API key.

Options:
  -i, --id TEXT  The UUID for the API key to delete.  [required]
  --help         Show this message and exit.
```

### status
```
Get the current Prefect authentication status

Options:
  --help  Show this message and exit.
```

### create-token
```
DEPRECATED. Please use API keys instead.

Create a Prefect Cloud API token.

For more info on API tokens visit
https://docs.prefect.io/orchestration/concepts/api.html

Options:
    --name, -n      TEXT    A name to give the generated token
    --scope, -s     TEXT    A scope for the token
```

### list-tokens
```
DEPRECATED. Please use API keys instead.

  List your available Prefect Cloud API tokens.

Options:
  --help  Show this message and exit.
```

### revoke-token
```
DEPRECATED. Please use API keys instead.

Revote a Prefect Cloud API token

Options:
    --id, -i    TEXT    The id of a token to revoke
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>