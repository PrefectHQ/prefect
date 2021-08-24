---
sidebarDepth: 2
editLink: false
---
# auth
---
### login
```
Log in to Prefect Cloud with an api token to use for Cloud communication.

Options:
    --token, -t         TEXT    A Prefect Cloud api token  [required]
```

### logout
```
Log out of Prefect Cloud

Options:
  --help  Show this message and exit.
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

### create-token
```
Create a Prefect Cloud API token.

For more info on API tokens visit
https://docs.prefect.io/orchestration/concepts/api.html

Options:
    --name, -n      TEXT    A name to give the generated token
    --scope, -s     TEXT    A scope for the token
```

### list-tokens
```
List your available Prefect Cloud API tokens.

Options:
  --help  Show this message and exit.
```

### revoke-token
```
Revote a Prefect Cloud API token

Options:
    --id, -i    TEXT    The id of a token to revoke
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>