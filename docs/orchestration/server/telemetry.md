# Telemetry

Prefect Server sends usage telemetry and statistics to Prefect Technologies, Inc. All information collected is anonymous. We use this information to better understand how Prefect Server is used and to ensure that we're supporting active versions.

To opt-out of telemetry, add the following to a user configuration file on the same machine as your Prefect Server instance (wherever you're calling `prefect server start`). See [user configuration](/core/concepts/configuration.md#user-configuration) for more details.

```toml
[server.telemetry]
enabled = false
```

See [configuration](/core/concepts/configuration.md) for a complete overview of configuration.
