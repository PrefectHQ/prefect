# Configuration Options

A full list of configuation options can be seen in the Prefect [config.toml](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/config.toml). 

## Running Prefect with a pre-exisiting postgres database
If you have a postgres instance set up elsewhere then providing a connection string like this through the config var:

```
[server.database]
connection_url = ...
```

will override the default.  You could also update the database host. 