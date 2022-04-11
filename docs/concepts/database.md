---
description: Learn more about Prefect Orion database use and configuration.
tags:
    - Orion
    - database
    - metadata
    - SQLite
    - PostgreSQL
---

# Orion Database

The Orion database persists data used by many features of Orion to orchestrate and track the state of your flow runs, including:

- Flow and task state
- Run history
- Logs
- Deployments
- Flow and task run concurrency limits
- Storage locations for flow and task results
- Work queue configuration and status

Currently Orion supports the following databases:

- SQLite: the default in Orion, and our recommendation for lightweight, single-server deployments. SQLite requires essentially no setup.
- PostgreSQL: best for connecting to external databases, but does require additional setup (such as Docker).

## Using the database

A local SQLite database is the default for Orion, and a local SQLite database is configured on installation.

When you first install Orion, your database will be located at `~/.prefect/orion.db`.

If at any point in your testing you'd like to reset your database, run the CLI command:  

```bash
$ prefect orion database reset -y
```

This will completely clear all data and reapply the schema.


## Configuring the database

To configure the database location, you can specify a connection URL with the `PREFECT_ORION_DATABASE_CONNECTION_URL` environment variable:

```bash
$ export PREFECT_ORION_DATABASE_CONNECTION_URL="sqlite+aiosqlite:////full/path/to/a/location/orion.db"
```

## Configuring a PostgreSQL database

To connect Orion to a PostgreSQL database, you can set the following environment variable:

```bash
$ export PREFECT_ORION_DATABASE_CONNECTION_URL="postgresql+asyncpg://postgres:yourTopSecretPassword@localhost:5432/orion"
```

The above environment variable assumes that:

- You have a username called `postgres`
- Your password is set to `yourTopSecretPassword`
- Your database runs on the same host as the Orion instance, `localhost`
- You use the default PostgreSQL port `5432`
- Your PostgreSQL instance has a database called `orion`

If you want to quickly start a PostgreSQL instance that can be used as your Orion database, you can use the following command that will start a Docker container running PostgreSQL:

```bash
$ docker run -d --name orion_postgres -v oriondb:/var/lib/postgresql/data -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=yourTopSecretPassword -e POSTGRES_DB=orion postgres:latest
```

The above command:

- Pulls the [latest](https://hub.docker.com/_/postgres?tab=tags) version of the official `postgres` Docker image, which is compatible with Prefect 2.0
- Starts a container with the name `orion_postgres`
- Creates a database `orion` with a user `postgres` and `yourTopSecretPassword` password
- Mounts the PostgreSQL data to a Docker volume called `oriondb` to provide persistence if you ever have to restart or rebuild that container

You can inspect your profile to be sure that the environment variable has been set properly:

```bash
$ prefect config view --show-sources
```

Start Orion and it should from now on use your PostgreSQL database instance:

```bash
$ prefect orion start
```

## In-memory databases

One of the benefits of SQLite is in-memory database support. 

To use an in-memory SQLite database, set the following environment variable:

```bash
$ export PREFECT_ORION_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false"
```

!!! warning "In-memory databases for testing only"
    In-memory databases are only supported in Orion for testing purposes and are not compatible with multiprocessing.  


## Database versions

The following database versions are required for use with Prefect:

- SQLite 3.24 or newer
- PostgreSQL 13.0 or newer
