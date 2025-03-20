# Migration notes

Each time a database migration is written, an entry is included here with:

- The purpose of the migration
- Concerns about upgrade / downgrade (if any)
- Revision numbers for sqlite/postgres

This gives us a history of changes and will create merge conflicts if two migrations are made at once, flagging situations where a branch needs to be updated before merging.

# Add `deployment_version` table
SQLite: `bbca16f6f218`
Postgres: `06b7c293bc69`

# Add `storage_configuration` to work pool
SQLite: `3457c6ca2360`
Postgres: `b5f5644500d2`

# Add parameters column to deployment schedules
SQLite: `67f886da208e`
Postgres: `c163acd7e8e3`

# Bring ORM models and migrations back in sync
SQLite: `a49711513ad4`
Postgres: `5d03c01be85e`

# Add `labels` column to Flow, FlowRun, TaskRun, and Deployment
SQLite: `5952a5498b51`
Postgres: `68a44144428d`

# Migrate `Deployment.concurrency_limit` to a foreign key `Deployment.concurrency_limit_id`
SQLite: `4ad4658cbefe`
Postgres: `eaec5004771f`

# Adds `concurrency_options` to `Deployments`
SQLite: `7d6350aea855`
Postgres: `555ed31b284d`

# Add `concurrency_limit` to `Deployments`
SQLite: `f93e1439f022`
Postgres:`97429116795e`

# Add `events` and `event_resources` tables
SQLite: `824e9edafa60`
Postgres: `15768c2ec702`

# Add `trigger_id` to the unique index for `automation_bucket`
SQLite: `2b6c2b548f95`
Postgres: `954db7517015`

# Create `csrf_token` table
SQLite: `bacc60edce16`
Postgres: `7a653837d9ba`

# Add `job_variables` to `flow_runs`
SQLite: `342220764f0b`
Postgres: `121699507574`

# Create `deployment_schedule` and add `Deployment.paused`
SQLite: `265eb1a2da4c`
Postgres: `8cf4d4933848`

# Add `sender` to `FlowRunInput`
SQLite: `c63a0a6dc787`
Postgres: `6b63c51c31b4`

# Make `FlowRunInput.flow_run_id` a foreign key to `flow_run.id`
SQLite: `a299308852a7`
Postgres: `7c453555d3a5`

# Add `flow_run_input` table
SQLite: `a299308852a7`
Postgres: `733ca1903976`

# Add last_polled to deployment table
SQLite: `f3165ae0a213`
Postgres: `bfe653bbf62e`

# Make flow_run_id nullable on task_run and log tables
SQLite: `05ea6f882b1d`
Postgres: `05ea6f882b1d`

# Make slot_decay_per_second not nullable
SQLite: `8167af8df781`
Postgres: `4e9a6f93eb6c`

# Add heartbeat_interval_seconds to worker table
SQLite: `c2d001b7dd06`
Postgres: `50f8c182c3ca`

# Create Concurrency Limit V2 table
SQLite: `5b0bd3b41a23`
Postgres: `5f623ddbf7fe`

# Migrate Artifact data to Artifact Collection
SQLite: `2dbcec43c857`
Postgres: `15f5083c16bd`

# Add Variables Table
SQLite: `3d46e23593d6`
Postgres: `310dda75f561`

# Add pull steps to deployment table
SQLite: `340f457b315f`
Postgres: `43c94d4c7aa3`

# Add Artifact Collection columns
SQLite: `3e1eb8281d5e`
Postgres: `6a1eb3d442e4`

# Add index on log table
SQLite: `553920ec20e9`
Postgres: `3bf47e3ce2dd`

# Add Artifact index
SQLite: `422f8ba9541d`
Postgres: `46bd82c6279a`

# Add Artifact Collection table
SQLite: `b9aafc3ab936`
Postgres: `d20618ce678e`

# Remove Artifact unique constraint
SQLite: `1d7441c031d0`
Postgres: `aa84ac237ce8`

# Add Artifact description column
SQLite: `cf1159bd0d3c`
Postgres: `4a1a0e4f89de`

# Remove Flow Run foreign keys
SQLite: `f3df94dca3cc`
Postgres: `7d918a392297`

# Remove Artifact foreign keys
SQLite: `8d148e44e669`
Postgres: `cfdfec5d7557`

# Clean up work queue migration
SQLite: `bfe42b7090d6`
Postgres: `2a88656f4a23`

# Work queue data migration
SQLite: `1678f2fb8b33`
Postgres: `f98ae6d8e2cc`

# Expands Work Queue Table
SQLite: `b9bda9f142f1`
Postgres: `0a1250a5aa25`

# State data migration cleanup
SQLite: `f92143d30c27`
Postgres: `2882cd2df466`

# Migrates state data to the artifact table
SQLite: `f92143d30c26`
Postgres: `2882cd2df465`

# Add a helper index for the artifact data migration
SQLite: `f92143d30c25`
Postgres: `2882cd2df464`

# Initial schema migration for the artifacts/results table
SQLite: `f92143d30c24`
Postgres: `2882cd2df463`

This schema migration creates the artifact table with extra `state_id` columns in order speed up the data migration.

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

Adds a table for storing key / value configuration options for Prefect REST API in the database.

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

## Initial

Creates the database that previously was not managed by migrations.

Upgrading to an existing database to use migrations requires the use of `prefect database alembic stamp` before a reset will drop existing tables.

SQLite: `9725c1cbee35`
Postgres: `25f4b90a7a42`
