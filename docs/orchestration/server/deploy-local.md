# Deploying to a single node

Prefect Server can be deployed on a single node using a
[docker-compose](https://docs.docker.com/compose/) setup. One way to accomplish this is to use the
builtin command in the Prefect CLI. Note that this requires both `docker-compose` and `docker` to be installed.

```bash
prefect server start
```

Note that this command may take a bit to complete, as the various docker images are pulled. Once running,
you should see some "Prefect Server" ASCII art along with the logs output from each service, and the UI should be available at
[http://localhost:8080](http://localhost:8080).

For more information on running the server in development mode without Docker see the
[developer documentation](/orchestration/server/development.html).

## UI configuration

By default the UI will attempt to communicate with the Apollo endpoint at
[http://localhost:4200/graphql](http://localhost:4200/graphql). If users should access Apollo at a
different location (e.g. if you're running Prefect Server behind a proxy), you'll need to configure the
proper URL before running `prefect server start`.

You can do this via the [Prefect configutation](/core/concepts/configuration.html#user-configuration),
using either an environment variable or the `~/.prefect/config.toml` file:

:::: tabs
::: tab "Environment Variable"
```bash
export PREFECT_SERVER__UI__GRAPHQL_PORT=<YOUR_APOLLO_URL>
```
:::

::: tab config.toml
```toml
# ~/.prefect/config.toml
[server]
    [server.ui]
        graphql_url = "<YOUR_APOLLO_URL>"
```
:::
::::

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

## How to upgrade your server instance

When new versions of the server are released you will want to upgrade in order to stay on top of fixes,
enhancements, and new features. When running the server in containers using Docker compose an upgrade
should be as simple as stopping the instance, installing the most recent version of prefect, and then
starting the server again. Note that you'll want to be using a [persistent
volume](/orchestration/server/deploy.html#database-persistence-and-migrations) for Postgres to ensure
that your metadata is not lost between restarts.

Due to the current implementation of the single node deployment for server this will result in a small
window of downtime. If high availability is important for your instance it is encouraged that you inquire
about a community maintained deployment method or sign up for a free developer account at
[Prefect Cloud](https://cloud.prefect.io).
