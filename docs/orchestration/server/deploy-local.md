# Deploying to a single node

Prefect Server can be deployed on a single node using [docker-compose](https://docs.docker.com/compose/). 

The easiest way accomplish this is to use the built-in command in the Prefect CLI.
Note that this requires both `docker-compose >= 1.18.0` and `docker` to be installed.

```bash
prefect server start
```

Note that this command may take a bit to complete, as the various docker images are pulled. Once running,
you should see some "Prefect Server" ASCII art along with the logs output from each service, and the UI should be available at
[http://localhost:8080](http://localhost:8080).

::: tip Installing Docker
We recommend installing [Docker Desktop](https://www.docker.com/products/docker-desktop) following their instructions then installing docker-compose with `pip install docker-compose`.
:::


::: tip Just show me the config
`prefect server start` templates a basic docker-compose file to conform to the options you pass. Sometimes, you just want to generate this file then manage running it yourself (or make further customizations). We provide a `prefect server config` command that takes all the same settings as `prefect server start` and prints the file to stdout. Try piping it to a file `prefect server config > docker-compose.yaml`.
:::

## UI configuration

By default the UI will attempt to communicate with the Apollo endpoint at
[http://localhost:4200/graphql](http://localhost:4200/graphql). If users should access Apollo at a
different location (e.g. if you're running Prefect Server behind a proxy), you'll need to configure the UI
to look at a different URL.

You can set this directly in the UI on the Home page:

![UI Endpoint Setting](/orchestration/server/server-endpoint.png)

...or by setting `apollo_url` in `~/.prefect/config.toml` on whatever machine you're running Prefect Server:

```
[server]
  [server.ui]
  apollo_url="http://localhost:4200/graphql"
```

Note: The second method will change the _default_ Apollo endpoint but can still be overidden by the UI setting.

::: tip You don't need to host the UI yourself!
Because the UI is code that runs in your browser, you can reuse Prefect Cloud's hosted UI for local purposes!

To achieve this:

- [sign up for a free Developer account](https://cloud.prefect.io/)
- login; if you click the Prefect Cloud logo at the bottom of the left menu bar, the UI will switch the endpoint that it talks to
- you can further configure the location of this endpoint on the Home page
  :::

## Database persistence and migrations

If you want Prefect Server to persist data across restarts, then you'll want to run the Postgres service
using a mounted volume. When running the server with the `prefect server start` command there are two
options you can set to automatically use of a volume for Postgres:

- `--use-volume`: enable the use of a volume for the Postgres database
- `--volume-path`: a path to use for the volume, defaults to `~/.prefect/pg_data` if not provided

Every time you run the `prefect server start` command [a set of alembic migrations](https://github.com/PrefectHQ/server/tree/master/services/postgres/alembic/versions) are automatically
applied against the database to ensure the schema is consistent. To run the migrations directly please
see the documentation on [prefect server migrations](https://github.com/PrefectHQ/server#running-the-system).

### External Postgres instance

You can also configure Prefect Server to use an external Postgres instance.

The simplest way to specify an external Postgres instance is passing in a command line argument:

```bash
prefect server start --postgres-url postgres://<username>:<password>@hostname:<port>/<dbname>
```

You can also configure the database url in `~/.prefect/config.toml` on whatever machine you're running Prefect Server:

```
[server.database]
connection_url = "postgres://<username>:<password>@hostname:<port>/<dbname>"
```

And then run `prefect server start --external-postgres`. 

Using either method, the connection url will be passed directly to Hasura. For more information and troubleshooting, see the [docs](https://hasura.io/docs/latest/graphql/core/deployment/deployment-guides/docker.html#database-url).

Please note [a set of alembic migrations](https://github.com/PrefectHQ/server/tree/master/services/postgres/alembic/versions) are automatically applied against
the external database on start.

## How to upgrade your server instance

When new versions of the server are released you will want to upgrade in order to stay on top of fixes,
enhancements, and new features. When running the server in containers using Docker compose an upgrade
should be as simple as stopping the instance, installing the most recent version of prefect, and then
starting the server again. Note that you'll want to be using a [persistent
volume](/orchestration/server/deploy-local.md#database-persistence-and-migrations) for Postgres to ensure
that your metadata is not lost between restarts.

Due to the current implementation of the single node deployment for server this will result in a small
window of downtime. If high availability is important for your instance it is encouraged that you inquire
about a community maintained deployment method or sign up for a free developer account at
[Prefect Cloud](https://cloud.prefect.io).
