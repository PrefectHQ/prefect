# Prefect Integrations

Official integrations extending Prefect with external services and platforms.

## Available Integrations

- **Cloud**: AWS, GCP, Azure
- **Containers**: Docker, Kubernetes
- **Databases**: SQLAlchemy, Snowflake
- **Data Tools**: Dask, Ray, dbt, Databricks
- **Version Control**: GitHub, GitLab
- **Communication**: Slack, Email

## Integration Components

- **Blocks**: Connection configuration
- **Tasks**: Pre-built operations
- **Workers**: Infrastructure adapters
- **Storage**: Code and artifact storage

## Integration-Specific Notes

- Each integration is independently versioned
- Self-contained with own dependencies
- Follow common authentication patterns
- Use blocks for credentials, not raw values in flows