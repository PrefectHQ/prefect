---
description: The Prefect database stores deployment and flow run data.
tags:
    - database
    - metadata
    - migrations
    - SQLite
    - PostgreSQL
---

# Prefect Database

The Prefect database persists data used by many features of Prefect to persist and track the state of your flow runs, including:

- Flow and task state
- Run history
- Logs
- Deployments
- Flow and task run concurrency limits
- Storage blocks for flow and task results
- Work queue configuration and status

Currently Prefect supports the following databases:

- SQLite: The default in Prefect, and our recommendation for lightweight, single-server deployments. SQLite requires essentially no setup.
- PostgreSQL: Best for connecting to external databases, but does require additional setup (such as Docker). Prefect uses the [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html) extension, so it must be installed and enabled.

## Using the database

A local SQLite database is the default for Prefect. A local SQLite database is configured on installation.

When you first install Prefect, your database will be located at `~/.prefect/prefect.db`.

If at any point in your testing you'd like to reset your database, run the CLI command:  

<div class="terminal">
```bash
prefect server database reset -y
```
</div>

This will completely clear all data and reapply the schema.

## Configuring the database

To configure the database location, you can specify a connection URL with the `PREFECT_API_DATABASE_CONNECTION_URL` environment variable:

<div class="terminal">
```bash
prefect config set PREFECT_API_DATABASE_CONNECTION_URL="sqlite+aiosqlite:////full/path/to/a/location/prefect.db"
```
</div>

## Configuring a PostgreSQL database

To connect Prefect to a PostgreSQL database, you can set the following environment variable:

<div class="terminal">
```bash
prefect config set PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://postgres:yourTopSecretPassword@localhost:5432/prefect"
```
</div>

The above environment variable assumes that:

- You have a username called `postgres`
- Your password is set to `yourTopSecretPassword`
- Your database runs on the same host as the Prefect server instance, `localhost`
- You use the default PostgreSQL port `5432`
- Your PostgreSQL instance has a database called `prefect`

If you want to quickly start a PostgreSQL instance that can be used as your Prefect database, you can use the following command that will start a Docker container running PostgreSQL:

<div class="terminal">
```bash
docker run -d --name prefect-postgres -v prefectdb:/var/lib/postgresql/data -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=yourTopSecretPassword -e POSTGRES_DB=prefect postgres:latest
```
</div>

The above command:

- Pulls the [latest](https://hub.docker.com/_/postgres?tab=tags) version of the official `postgres` Docker image, which is compatible with Prefect.
- Starts a container with the name `prefect-postgres`.
- Creates a database `prefect` with a user `postgres` and `yourTopSecretPassword` password.
- Mounts the PostgreSQL data to a Docker volume called `prefectdb` to provide persistence if you ever have to restart or rebuild that container.

You can inspect your profile to be sure that the environment variable has been set properly:

<div class="terminal">
```bash
prefect config view --show-sources
```
</div>

Start the Prefect server and it should from now on use your PostgreSQL database instance:

<div class="terminal">
```bash
prefect server start
```
</div>

## In-memory databases

One of the benefits of SQLite is in-memory database support. 

To use an in-memory SQLite database, set the following environment variable:

<div class="terminal">
```bash
prefect config set PREFECT_API_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false"
```
</div>

!!! warning "In-memory databases for testing only"
    In-memory databases are only supported by Prefect for testing purposes and are not compatible with multiprocessing.  

## Database versions

The following database versions are required for use with Prefect:

- SQLite 3.24 or newer
- PostgreSQL 13.0 or newer


## Migrations

Prefect uses [Alembic](https://alembic.sqlalchemy.org/en/latest/) to manage database migrations. Alembic is a 
database migration tool for usage with the SQLAlchemy Database Toolkit for Python. Alembic provides a framework for 
generating and applying schema changes to a database.

### Running migrations
To apply migrations to your database you can run the following commands:

To upgrade:
<div class="terminal">
```bash
prefect server database upgrade -y
```
</div>
To downgrade:
<div class="terminal">
```bash
prefect server database downgrade -y
```
</div>

You can use the `-r` flag to specify a specific migration version to upgrade or downgrade to. 
For example, to downgrade to the previous migration version you can run:
<div class="terminal">
```bash
prefect server database downgrade -y -r -1
```
</div>
or to downgrade to a specific revision:
<div class="terminal">
```bash
prefect server database downgrade -y -r d20618ce678e
```
</div>

### Creating migrations
See the [contributing docs](/contributing/overview/#adding-database-migrations) for more information on how to create new migrations
