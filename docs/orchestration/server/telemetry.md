# Telemetry

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

Prefect Server sends usage telemetry and statistics to Prefect Technologies, Inc. All information collected is anonymous. We use this information to better understand how Prefect Server is used and to ensure that we're supporting active versions.

To opt-out of telemetry, add the following to a prefect server configuration file on the same machine as your Prefect Server instance (wherever you're calling `prefect server start`).

```toml
# ~/.prefect/config.toml

[telemetry]
    [server.telemetry]
        enabled = false
```

See [configuration](/core/concepts/configuration.md) for a complete overview of configuration.
