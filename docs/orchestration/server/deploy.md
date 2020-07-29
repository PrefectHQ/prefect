# Deploying the Server

## Building Blocks

Diagram WIP:

<div class="add-shadow">
  <img src="/orchestration/server/server-diagram.svg">
</div>

The Prefect server contains various services that are used in collaboration to provide a robust solution
for orchestration. Here is a short breakdown of each of the pieces:

- **UI**: the user inteface that provides a visual dashboard for mutating and querying metadata
- **PostgreSQL**: the database persistence layer where metadata is stored
- **Hasura**: the GraphQL API that layers on top of Postgres for querying metadata
- **GraphQL**: the server's business logic that exposes GraphQL mutations
- **Apollo**: the main endpoint for interacting with the server, stitching together both the Hasura and
GraphQL services
- **Towel**: a single service which runs utilities that are responsible for server maintenance
    - *scheduler*: schedules and creates new flow runs
    - *zombie killer*: marks task runs as failed if they stay in a running state without a heartbeat
    - *lazarus*: reschedules flow runs that maintain an unusual state for a period of time

Each service is designed to live inside user infrastructure and communicate directly with one another.
This can easily be accomplished by using the [single node](/orchestration/server/deploy.html#deploying-to-a-single-node) deployment strategy with Docker compose because the Docker compose stands up the server with a single
`prefect-server` network. The reason why the UI, flows, and agents do not need to live inside the same
infrastructure is because they all communicate with the server directly through the endpoint exposed by
the Apollo service. The goal here is that outside of setting up the server users should not need to care
about any of the services running behind the single Apollo endpoint.

## Deploying to a single node

The Prefect server is intended to run within [Docker](https://www.docker.com/) containers using
[Docker compose](https://docs.docker.com/compose/). In fact, the Prefect CLI provides a single command
for standing up the server on a single machine using Docker compose.

After ensuring that Docker and Docker compose are running you can start the server with:

```bash
prefect server start
```

::: tip All options
To see all options you can provide to the start command run it with the `--help` flag.
:::

Now you should see a trail of output from Docker compose starting each service and once all components
are running you can view the UI by visiting [https://localhost:8080](https://localhost:8080).

For more information on running the server in development mode without Docker see the
[developer documentation](link-here).

### Other deployment models

As it currently stands, a single node deployment using Docker compose is the only method officially
supported by the Prefect core development team. There are outstanding community efforts to create other
deployment models such as ECS, Kubernetes, etc. The core development team is planning on supporting more
out-of-the-box deployments in the near future.

## UI deployment and configuration

By default, the UI will look to communicate with the Apollo endpoint at `localhost:4200` however there
are instances where you stand up the server so it can be accessible from a different endpoint such as
behind a VPC. Due to the UI configuration being loaded at build-time the IP of the Apollo endpoint needs
to be set before the UI starts up. On the same machine that you use to host the UI you will need to set
the endpoint through the [Prefect configutation](/core/concepts/configuration.html#user-configuration).

If the machine does not already have a Prefect config you can create one like this:

```bash
mkdir ~/.prefect

touch ~/.prefect/config.toml
```

Then add the following lines to the `config.toml` we just created:

```
[server]
    [server.ui]
        graphql_url = "http://YOUR_APOLLO_ENDPOINT:4200/graphql
```

## Database persistence and migrations

If you want to maintain the persistence of the metadata that the server Postgres database contains then
you should run the server with a mounted volume. When running the server with the `prefect server start`
command there are two options you can set to automatically use of a volume for Postgres:

- `--use-volume`: enable the use of a volume for the Postgres database
- `--volume-path`: a path to use for the volume, defaults to `~/.prefect/pg_data` if not provided

Every time you run the `prefect server start` command a set of alembic migrations are automatically
applied against the database to ensure the schema is consistent. To run the migrations directly please
see the documentation on [prefect server migrations](link-to-how-to-use-server-package-migrations).

## How to upgrade server instance

When new versions of the server are released you will want to upgrade in order to stay on top of fixes,
enhancements, and new features. When running the server in containers using Docker compose an upgrade is
as simple as stopping the instance, installing the most recent version of prefect, and then starting the
server again. You are going to want to be using a [persistent volume](/orchestration/server/deploy.html#database-persistence-and-migrations) for Postgres to ensure that your
metadata is not lost in between restarts.

Due to the current implementation of the single node deployment for server this will result in a small
window of downtime. If high availability is important for your instance it is encouraged that you inquire
about a community maintained deployment method or sign up for a free developer account at
[Prefect Cloud](https://cloud.prefect.io).
