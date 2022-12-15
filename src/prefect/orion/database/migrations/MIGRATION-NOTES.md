# Migration notes

Each time a database migration is written, an entry is included here with:

- The purpose of the migration
- Concerns about upgrade / downgrade (if any)
- Revision numbers for sqlite/postgres

This gives us a history of changes and will create merge conflicts if two migrations are made at once, flagging situations where a branch needs to be updated before merging.

# Add `CANCELLING` to StateType enum
SQLite: None
Postgres: `9326a6aee18b`

# Add infrastructure_pid to flow runs
SQLite: `7201de756d85`
Postgres: `5d526270ddb4`

# Add index for partial work queue name match
SQLite: None
Postgres: `41e5ed9e1034`

# Add version to block schema
SQLite: `e757138e954a`
Postgres: `2d5e000696f1`

# Add work queue name to runs
SQLite: `575634b7acd4`
Postgres: `77eb737fc759`

## Add more fields to deployments

SQLite: `296e2665785f`
Postgres: `60e428f92a75`

## Fix concurrency limit tag index name

SQLite: `53c19b31aa09`
Postgres: `7737221bf8a4`

## Add deployment.version

SQLite: `24bb2e4a195c`
Postgres: `97e212ea6545`

## Breaking changes to Deployment schema

SQLite: `88c2112b668f`
Postgres: `add97ce1937d`

## Adds block type slug

SQLite: `f335f9633eec`
Postgres: `4ff2f2bf81f4`

## Add CRASHED canonical state

SQLite: None
Postgres: `0cf7311d6ea6`

## Renames existing block types and deletes removed block types

SQLite: `628a873f0d1a`
Postgres: `bb4dc90d3e29`
## Removing default storage block document

SQLite: `56be24fdb383`
Postgres: `0f27d462bf6d`

## Removes DebugPrintNotification block type

SQLite: `061c7e518b40`
Postgres: `e905fd199258`

## Migrates block schemas with new secrets fields

SQLite: `e2dae764a603`
Postgres: `4cdc2ba709a4`

## Add description column to deployment table

SQLite: `3bd87ecdac38`
Postgres: `813ddf14e2de`

## Remove name column for flow run notification policies

SQLite: `42762c37b7bc`
Postgres: `2f46fc3f3beb`

## Add protected column for block types

SQLite: `dff8da7a6c2c`
Postgres: `7296741dff68`

## Add indexes for block entity filtering

SQLite: `a205b458d997`
Postgres: `29ad9bef6147`
## Add indexes for block schemas

SQLite: `9e2a1c08c6f1`
Postgres: `d335ad57d5ba`

## Add anonymous column for block documents

SQLite: `2d900af9cd07`
Postgres: `61c76ee09e02`

## Add description to block types

SQLite: `84892301571a`
Postgres: `3a7c41d3b464`
## Add indexes for partial matches on names

SQLite: `f65b6ad0b869`
Postgres: `77ebcc9cf355`

## Rename Flow Run Alerts to Notifications

SQLite: `d76326ed0d06`
Postgres: `cdcb4018dd0e`

## Add BlockSchemas

SQLite: `33439667aeea`
Postgres: `d76326ed0d06`

## Add FlowRunAlertPolicy and FlowRunAlertQueue

SQLite: `888a0bb0df7b`
Postgres: `dc7a3c6fd3e9`

## Rename Block to BlockDocument and BlockSpec to BlockSchema

SQLite: `fd966d4ad99c`
Postgres: `d38c5e6a9115`
## Backfill state_name columns

SQLite: `db6bde582447`
Postgres: `14dc68cc5853`

Data only migration that backfills FlowRun.state_name and TaskRun.state_name.

## Add state_name columns

SQLite: `7f5f335cace3`
Postgres: `605ebb4e9155`

Adds FlowRun.state_name and TaskRun.state_name columns for more efficient querying.

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
