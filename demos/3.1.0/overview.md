# Runtime Configuration with prefect.toml

A demonstration of Prefect 3.1.0's new configuration capabilities using a data processing workflow.

## Overview

- Introduction to `prefect.toml`
- Demonstration flow processing large datasets
- Configuration patterns and best practices

## The Demo Flow

Our example processes a large dataset in concurrent chunks:

- Load and partition a configurable-sized dataset
- Process chunks in parallel
- Store results as artifacts

## Configuration with prefect.toml

```toml
[client]
# Resilient API interactions
max_retries = 5

[results]
# Persist results by default (defaults to local disk)
persist_by_default = true

# Choose to store results in S3 instead
default_storage_block = "s3-bucket/test-bucket"

[tasks]
# Number of threads to use for concurrent execution
runner.thread_pool_max_workers = 35
```

## Key Features Demonstrated

- Concurrent execution with configurable thread pool task runner
- Automatic result persistence
- Remote storage integration (e.g. local or s3)
- Task caching with configurable cache policy

## Configuration Patterns

- Version-controlled settings with `prefect.toml`
- Local development with `.env`
- Deployment-specific overrides
- Work pool configuration

## Development Workflow

- Team standardization via shared `prefect.toml`
- Local testing flexibility
- Production deployment configuration
