# Prefect Data Pipeline — OSOP Workflow Example

This directory contains a portable [OSOP](https://github.com/Archie0125/osop-spec) workflow definition for a typical Prefect ETL data pipeline.

## What is OSOP?

**OSOP** (Open Standard for Orchestration Protocols) is a YAML-based format for describing multi-step workflows in a tool-agnostic way. It lets you define pipelines, agent workflows, and automation flows that can be understood by any compatible runtime — including Prefect, Haystack, LangChain, and others.

Think of it as the **OpenAPI of workflows**: a single `.osop` file describes what your pipeline does, so teams can share, review, and port workflows across tools.

## Pipeline Overview

The `prefect-data-pipeline.osop` file describes an ETL pipeline with error handling:

```
Extract from API → Validate Schema → Transform Data → Load to Warehouse → Update Dashboard
         |                              |                    |
         └──────────────────────────────┴────────────────────┴──→ Notify on Failure
```

| Step | OSOP Node Type | Prefect Equivalent |
|------|---------------|-------------------|
| Extract from API | `api` | `@task` with HTTP client |
| Validate Schema | `system` | `@task` with schema validation |
| Transform Data | `agent` | `@task` with data processing |
| Load to Warehouse | `db` | `@task` with Snowflake connector |
| Update Dashboard | `api` | `@task` with API call |
| Notify on Failure | `api` | Prefect automation / Slack webhook |

## Key Features Shown

- **Retry logic**: The extract step includes `retry_policy` with max retries and backoff — maps directly to Prefect's `@task(retries=3, retry_delay_seconds=10)`
- **Error edges**: Multiple steps route to a failure notification node on error — maps to Prefect automations or `on_failure` hooks
- **Timeout**: The extract step has a `timeout_sec` — maps to Prefect's `@task(timeout_seconds=60)`

## Usage

The `.osop` file is a standalone YAML document. You can:

- **Read it** to understand the pipeline at a glance
- **Validate it** with the [OSOP CLI](https://github.com/Archie0125/osop): `osop validate prefect-data-pipeline.osop`
- **Visualize it** with the [OSOP Editor](https://github.com/Archie0125/osop-editor)
- **Use it as a reference** when building the equivalent Prefect flow in Python

## Links

- [OSOP Spec](https://github.com/Archie0125/osop-spec)
- [OSOP CLI](https://github.com/Archie0125/osop)
- [Prefect Documentation](https://docs.prefect.io/)
