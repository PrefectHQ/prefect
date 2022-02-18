# Migration notes

Each time a database migration is written, an entry is included here with:

- The purpose of the migration
- Concerns about upgrade / downgrade (if any)

This gives us a history of changes and will create merge conflicts if two migrations are made at once, flagging situtations where a branch needs to be updated before merging.

## Add configuration tables - 28ae48128c75

Adds a table for storing key / value configuration options for Orion in the database.

## Add agent and work queue tables - 7c91cb86dc4e

Adds tables for storing agent information and work queues.

## Add block storage - 619bea85701a

Adds tables for storing block data.

## Intial - 9725c1cbee35

Creates the database that previously was not managed by migrations.

Upgrading to an existing database to use migrations requires the use of `prefect database alembic stamp` before a reset will drop existing tables.