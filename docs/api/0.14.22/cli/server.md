---
sidebarDepth: 2
editLink: false
---
# server
---
### start
```
This command spins up all infrastructure and services for the Prefect Core
server

Options:
    --version, -v       TEXT    The server image versions to use (for example, '0.1.0'
                                or 'master'). Defaults to `core-a.b.c` where `a.b.c.`
                                is the version of Prefect Core currently running.
    --ui-version, -uv   TEXT    The UI image version to use (for example, '0.1.0' or
                                'master'). Defaults to `core-a.b.c` where `a.b.c.` is
                                the version of Prefect Core currently running.
    --no-upgrade, -n            Flag to avoid running a database upgrade when the
                                database spins up
    --no-ui, -u                 Flag to avoid starting the UI

    --external-postgres, -ep    Disable the Postgres service, connect to an external one instead
    --postgres-url      TEXT    Postgres connection url to use. Expected format
                                is postgres://<username>:<password>@hostname:<port>/<dbname>

    --postgres-port     TEXT    Port used to serve Postgres, defaults to '5432'.
                                Not valid for external Postgres.
    --hasura-port       TEXT    Port used to serve Hasura, defaults to '3000'
    --graphql-port      TEXT    Port used to serve the GraphQL API, defaults to '4201'
    --ui-port           TEXT    Port used to serve the UI, defaults to '8080'
    --server-port       TEXT    Port used to serve the Core server, defaults to '4200'

    --no-postgres-port          Disable port map of Postgres to host.
                                Not valid for external Postgres.
    --no-hasura-port            Disable port map of Hasura to host
    --no-graphql-port           Disable port map of the GraphQL API to host
    --no-ui-port                Disable port map of the UI to host
    --no-server-port            Disable port map of the Core server to host

    --use-volume                Enable the use of a volume for the Postgres service.
                                Not valid for external Postgres.
    --volume-path       TEXT    A path to use for the Postgres volume, defaults to
                                '~/.prefect/pg_data' Not valid for external Postgres.

    --detach, -d                Detached mode. Runs Server containers in the background
    --skip-pull                 Flag to skip pulling new images (if available)
```

### create-tenant
```
This command creates a tenant for the Prefect Server

Options:
    --name, -n       TEXT    The name of a tenant to create
    --slug, -n       TEXT    The slug of a tenant to create (optional)
```

### stop
```
This command stops all Prefect Server containers that are connected to the
  `prefect-server` network. Note: This will completely remove the `prefect-
  server` network and all associated containers.

Options:
  --help  Show this message and exit.
```

### config
```
This command writes the configured docker-compose.yml file to standard
output

Options:
    --version, -v       TEXT    The server image versions to use (for example, '0.1.0'
                                or 'master'). Defaults to `core-a.b.c` where `a.b.c.`
                                is the version of Prefect Core currently running.
    --ui-version, -uv   TEXT    The UI image version to use (for example, '0.1.0' or
                                'master'). Defaults to `core-a.b.c` where `a.b.c.` is
                                the version of Prefect Core currently running.
    --no-upgrade, -n            Flag to avoid running a database upgrade when the
                                database spins up
    --no-ui, -u                 Flag to avoid starting the UI

    --external-postgres, -ep    Disable the Postgres service, connect to an external one instead
    --postgres-url      TEXT    Postgres connection url to use. Expected format is
                                postgres://<username>:<password>@hostname:<port>/<dbname>

    --postgres-port     TEXT    Port used to serve Postgres, defaults to '5432'.
                                Not valid for external Postgres.
    --hasura-port       TEXT    Port used to serve Hasura, defaults to '3000'
    --graphql-port      TEXT    Port used to serve the GraphQL API, defaults to '4201'
    --ui-port           TEXT    Port used to serve the UI, defaults to '8080'
    --server-port       TEXT    Port used to serve the Core server, defaults to '4200'

    --no-postgres-port          Disable port map of Postgres to host.
                                Not valid for external Postgres.
    --no-hasura-port            Disable port map of Hasura to host
    --no-graphql-port           Disable port map of the GraphQL API to host
    --no-ui-port                Disable port map of the UI to host
    --no-server-port            Disable port map of the Core server to host

    --use-volume                Enable the use of a volume for the Postgres service.
                                Not valid for external Postgres.
    --volume-path       TEXT    A path to use for the Postgres volume, defaults to
                                '~/.prefect/pg_data'. Not valid for external Postgres.
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>