# Configuration Options

A full list of configuation options can be seen in the Prefect [config.toml](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/config.toml). To update configuration settings you can update them in ./prefect/config.toml or by [environment varia]bles](/core/concepts/configuration.html#environment-variables). 

## Connecting to a different API Endpoint
If you are running Prefect Server, you can update the server.host and server.port config settings to point to a new API endpoint.

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

## Running Prefect with a pre-exisiting postgres database
If you are running Prefect Server and have a postgres instance set up elsewhere then providing a server.database.connection_url will allow you to connect to it:

```
[server.database]
connection_url = ...

```

You could also update the database host. 