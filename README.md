<p align="center"><img src="docs/img/logos/orion_logo.jpg" width=500></p>

# Orion

A development repo for Prefect Orion; reference documentation can be found at https://orion-docs.prefect.io/

## Installation

```bash
$ git clone https://github.com/PrefectHQ/prefect.git
$ cd prefect/
$ git checkout orion
$ pip install -e ".[dev]"
```

## Running the Orion server

*Please note steps 1 and 2 are optional. The Orion server will use an in-memory SQLite database by default. If using the in-memory default database, migrations will occur automatically and the database will not persist data when the server is stopped.*
### Step 1: Configure the database connection

Orion server works against SQLite and Postgresql. To specify which database to connect to, set the `PREFECT_ORION_DATABASE_CONNECTION_URL` environment variable.

To connect to a SQLite database (easiest/recommended option):

```bash
export PREFECT_ORION_DATABASE_CONNECTION_URL=sqlite+aiosqlite:////tmp/orion.db
```

To connect to a Postgres database, the connection string should look something like this:

```bash
export PREFECT_ORION_DATABASE_CONNECTION_URL=postgresql+asyncpg://<username>:<password>@<hostname>/<dbname>'
```

### Step 2: Ensuring database is up to date

For the time being, there is no framework for migrations. "Migrating" the database consists of creating the correct tables.

To migrate the database, run the following two lines in a python repl

```python
import prefect, asyncio
asyncio.run(prefect.orion.utilities.database.create_db())
```

Note that for SQLite databases, models are created automatically if the database is in-memory or is being created for the first time.

### Step 3: Running the server

Use the following command to run an Orion server locally:

```bash
uvicorn prefect.orion.api.server:app --reload
```

The `--reload` flag will automatically reload when changes are made the source files.

### Step 4: Interacting with the Orion REST API

The Orion server features interactive documentation, which will **actually make requests against the server and trigger database changes**.

After starting the server, navigate to `localhost:4200/docs`. On this page, you'll find documentation of requests and responses for all endpoints. The docs also pre-populate example data you can use to test out requests.
