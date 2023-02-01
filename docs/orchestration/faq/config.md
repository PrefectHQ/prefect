# Configuration Options

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

A full list of configuration options can be seen in the Prefect [config.toml](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/config.toml). To update configuration settings you can update them in `./prefect/config.toml` or by setting [environment variables](/core/concepts/configuration.html#environment-variables).

For more on configuration, you can also see the [Prefect Core configuration docs](/core/concepts/configuration.html).

## Connecting to a different API Endpoint
If you are running Prefect Server, you can update the `server.host` and `server.port` config settings to point to a new API endpoint.

```
[server]
host = ...
port = ...
```

As with all configuration options, you can update these using environment variables as well:

```
PREFECT__SERVER__HOST
PREFECT__SERVER__PORT
```

## Running Prefect with a pre-existing postgres database
If you are running Prefect Server and have a postgres instance set up elsewhere then providing a `server.database.connection_url` or `server.database.host` will allow you to connect to it:

```
[server.database]
connection_url = ...
host= ...
```
The connection_url format is: 

```
postgresql://username:password@host:port/database_name
```