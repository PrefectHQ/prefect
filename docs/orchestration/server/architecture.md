# Architecture

![Server Architecture](/orchestration/server/server-diagram.svg)

Prefect Server is composed of a few different services:

- **UI**: the user interface that provides a visual dashboard for mutating and querying metadata
- **Apollo**: the main endpoint for interacting with the server
- **PostgreSQL**: the database persistence layer where metadata is stored
- **Hasura**: the GraphQL API that layers on top of Postgres for querying metadata
- **GraphQL**: the server's business logic that exposes GraphQL mutations
- **Towel**: runs utilities that are responsible for server maintenance
    - *Scheduler*: schedules and creates new flow runs
    - *Zombie Killer*: marks task runs as failed if they fail to heartbeat
    - *Lazarus*: reschedules flow runs that maintain an unusual state for a period of time

Users and Agents only need access to the **Apollo** endpoint, all other services may reside behind a
firewall.
