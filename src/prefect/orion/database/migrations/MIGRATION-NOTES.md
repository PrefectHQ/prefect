# Migration notes

Each time a database migration is written, an entry is included here with:

- The purpose of the migration
- Concerns about upgrade / downgrade (if any)
- Revision numbers for sqlite/postgres

This gives us a history of changes and will create merge conflicts if two migrations are made at once, flagging situtations where a branch needs to be updated before merging.
## Add block spec id to blocks

SQLite: `c8ff35f94028`
Postgres: `b68b3cad6b8a`

## Index FlowRun.flow_runner_type

SQLite: `f327e877e423`
Postgres: `d115556a8ab6`

Indexes FlowRun.flow_runner_type for more efficient querying.
## Add block spec table

SQLite: `e1ff4973a9eb`
Postgres: `4799f657a6a1`

## Rename block data table

SQLite: `4c4a6a138053`
Postgres: `d9d98a9ebb6f`

## Add configuration tables

Adds a table for storing key / value configuration options for Orion in the database.

SQLite: `28ae48128c75`
Postgres: `679e695af6ba`

## Add agent and work queue tables

Adds tables for storing agent information and work queues.

SQLite: `7c91cb86dc4e`
Postgres: `5bff7878e700`

## Add block storage

Adds tables for storing block data.

SQLite: `619bea85701a`
Postgres: `5f376def75c3`

## Intial

Creates the database that previously was not managed by migrations.

Upgrading to an existing database to use migrations requires the use of `prefect database alembic stamp` before a reset will drop existing tables.

SQLite: `9725c1cbee35`
Postgres: `25f4b90a7a42`