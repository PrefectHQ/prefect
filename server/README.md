# Prefect Core's Server and UI

Spinning up Prefect Core's backend, API and UI locally can be achieved with a single command:

```
prefect server start
```

To ensure that your local Flow runs are pointing to your local backend (instead of Prefect Cloud), run:

```
prefect backend server
```

**Note:** Prefect Server requires both Docker and Docker Compose.

## Development

### Installation

To create a development environment for Prefect's server you will need:

- Python 3.7+
- Docker and Docker Compose
- `npm` installed

First, install an editable version of the `prefect-server` package:

```
git clone https://github.com/PrefectHQ/prefect.git
cd prefect/server
pip install -e .
```

If you wish to develop on the UI, you will also need to install the relevant dependencies:

```
cd server/services/ui
npm install
```

Depending on whether you will run the Apollo server via Docker or locally, you may also need to install its dependencies as well:

```
cd server/services/apollo
npm install
```

There is also a convenience `prefect-server dev install-dependencies` command which will perform both installs above for you.

### Spinning up pieces of the stack

At this point, there are various CLI commands which help you isolate the portion of the stack that you are working on:

For working on the API:

- `prefect-server dev infrastructure` will spin up both PostgreSQL and Hasura
- `prefect-server database upgrade -y` will then run all database migrations
- `prefect-server database reset -y` will completely reset your database (including performing all migrations)

You can then run the various services in subprocesses using the `prefect-server dev services` CLI command:

- `prefect-server dev services` will run _all_ services (apollo, graphql, scheduler and the UI) in hot-reloading subprocesses
- `prefect-server dev services -i X,Y,Z` will only run those services that you explicitly provide

For working on the UI:

- `prefect server start --no-ui` will spin up the standard backend with no UI
- `cd server/services/ui && npm run serve` will then run the UI in your local process, with hot reloading

## License

The contents of this directory are licensed under the Prefect Community License, which may be viewed in the LICENSE file in this directory or [https://www.prefect.io/legal/prefect-community-license](https://www.prefect.io/legal/prefect-community-license).
