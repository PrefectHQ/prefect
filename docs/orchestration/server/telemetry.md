# Telemetry

Prefect Server sends usage telemetry and statistics to Prefect Technologies, Inc. All information collected is anonymous. We use this information to better understand how Prefect Server is used and to ensure that we're supporting active versions.

To opt-out of telemetry, add the following to a prefect server configuration file on the same machine as your Prefect Server instance (wherever you're calling `prefect server start`).

```toml
# ~/.prefect_server/config.toml

[telemetry]
enabled = false
```

See [configuration](/core/concepts/configuration.md) for a complete overview of configuration.
