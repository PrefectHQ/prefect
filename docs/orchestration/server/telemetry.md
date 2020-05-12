# Telemetry

Prefect Server sends usage telemetry and statistics to Prefect Technologies, Inc. All information collected is anonymous. We use this information to better understand how Prefect Server is used and to ensure that we're supporting active versions.

To opt-out of telemetry, add the following to your user configuration file (see [user configuration](../../core/concepts/configuration.md#user-configuration)).

```toml
[server.telemetry]
enabled = false
```

As an environment variable this would be:

```bash
export PREFECT_SERVER__TELEMETRY__ENABLED=false
```

See [configuration](../../core/concepts/configuration.md) for more details.
