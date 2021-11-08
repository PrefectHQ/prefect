# Deploying to a single node

Prefect Server can be deployed on a single node using [docker-compose](https://docs.docker.com/compose/). 

The easiest way accomplish this is to use the built-in command in the Prefect CLI.
Note that this requires both `docker-compose >= 1.18.0` and `docker` to be installed.

```bash
prefect server start
```


::: warning Changes in Prefect 0.15.5
To start Prefect Server on a remote compute instance (such as AWS, GCP, ...), make sure to add the `--expose` flag, which ensures that the Server and UI listen to all interfaces. Under the hood, this flag changes the host IP to "0.0.0.0" instead of using the default localhost.

```bash
prefect server start --expose
```


This flag was introduced in [0.15.5](https://github.com/PrefectHQ/prefect/pull/4821) - if you use an older version of Prefect, you should skip it. 
:::


Note that this command may take a bit to complete, as the various docker images are pulled. Once running,
you should see some "Prefect Server" ASCII art along with the logs output from each service, and the UI should be available at
[http://localhost:8080](http://localhost:8080).


::: tip Installing Docker
We recommend installing [Docker Desktop](https://www.docker.com/products/docker-desktop) following their instructions then installing docker-compose with `pip install docker-compose`.
:::


::: tip Just show me the config
`prefect server start` templates a basic docker-compose file to conform to the options you pass. Sometimes, you just want to generate this file then manage running it yourself (or make further customizations). We provide a `prefect server config` command that takes all the same settings as `prefect server start` and prints the file to stdout. Try piping it to a file `prefect server config > docker-compose.yaml`.
:::

## UI configuration

By default the UI will attempt to communicate with the Apollo endpoint at
[http://localhost:4200/graphql](http://localhost:4200/graphql). If users should access Apollo at a
different location (e.g. if you're running Prefect Server behind a proxy), you'll need to configure the UI
to look at a different URL.

You can set this directly in the UI on the Home page:

![UI Endpoint Setting](/orchestration/server/server-endpoint.png)

...or by setting `apollo_url` in `~/.prefect/config.toml` on whatever machine you're running Prefect Server:

```
[server]
  [server.ui]
  apollo_url="http://localhost:4200/graphql"
```

Note: The second method will change the _default_ Apollo endpoint but can still be overidden by the UI setting.

::: tip You don't need to host the UI yourself!
Because the UI is code that runs in your browser, you can reuse Prefect Cloud's hosted UI for local purposes!

To achieve this:

- [sign up for a free account](https://cloud.prefect.io/)
- login; if you click the status indicator to the right of the nav-bar, the UI will switch the endpoint that it talks to
- you can further configure the location of this endpoint on the Home page
  :::

## Database persistence and migrations

If you want Prefect Server to persist data across restarts, then you'll want to run the Postgres service
using a mounted volume. When running the server with the `prefect server start` command there are two
options you can set to automatically use of a volume for Postgres:

- `--use-volume`: enable the use of a volume for the Postgres database
- `--volume-path`: a path to use for the volume, defaults to `~/.prefect/pg_data` if not provided

Every time you run the `prefect server start` command [a set of alembic migrations](https://github.com/PrefectHQ/server/tree/master/services/postgres/alembic/versions) are automatically
applied against the database to ensure the schema is consistent. To run the migrations directly please
see the documentation on [prefect server migrations](https://github.com/PrefectHQ/server#running-the-system).

### External Postgres instance

You can also configure Prefect Server to use an external Postgres instance.

The simplest way to specify an external Postgres instance is passing in a command line argument:

```bash
prefect server start --postgres-url postgres://<username>:<password>@hostname:<port>/<dbname>
```

You can also configure the database url in `~/.prefect/config.toml` on whatever machine you're running Prefect Server:

```
[server.database]
connection_url = "postgres://<username>:<password>@hostname:<port>/<dbname>"
```

And then run `prefect server start --external-postgres`. 

Using either method, the connection url will be passed directly to Hasura. For more information and troubleshooting, see the [docs](https://hasura.io/docs/latest/graphql/core/deployment/deployment-guides/docker.html#database-url).

Please note [a set of alembic migrations](https://github.com/PrefectHQ/server/tree/master/services/postgres/alembic/versions) are automatically applied against
the external database on start.

## How to upgrade your server instance

When new versions of the server are released you will want to upgrade in order to stay on top of fixes,
enhancements, and new features. When running the server in containers using Docker compose an upgrade
should be as simple as stopping the instance, installing the most recent version of prefect, and then
starting the server again. Note that you'll want to be using a [persistent
volume](/orchestration/server/deploy-local.md#database-persistence-and-migrations) for Postgres to ensure
that your metadata is not lost between restarts.

Due to the current implementation of the single node deployment for server this will result in a small
window of downtime. If high availability is important for your instance it is encouraged that you inquire
about a community maintained deployment method or sign up for a free developer account at
[Prefect Cloud](https://cloud.prefect.io).

## Troubleshooting

If you're having trouble starting Prefect Server, check this section for common solutions.


### How to know if there's a problem

After running `prefect server start`, you should be able to view the Prefect UI in a web browser at the address [http://localhost:8080](http://localhost:8080). This can work even if the server hasn't fully started yet.

You'll know there's a problem if the color of the connection menu in the upper-right-corner Prefect UI transitions between yellow and red, and never turns green.

You will see the message `Couldn't connect to Prefect Server at http://localhost:4200/graphql` when you click on the connection menu.

![](/orchestration/server/could-not-connect.png)

**Don't panic!** The troubleshooting steps in this section might help.

### The Hasura container failed to start

After you run `prefect server start`, the server's Docker containers should eventually start. However, the Hasura container might fail to start if Docker doesn't have enough memory.

When this happens, the following message will appear in your terminal after you run `prefect server start`:

```
t-hasura-1 exited with code 137
```

::: tip Finding this line
You may need to search with your terminal to find this line of output -- it won't be the last line printed.
:::

The solution to this problem is giving Docker more memory. The default in Docker Desktop is 2 GB, which may not be enough to run Prefect Server. We recommend giving Docker at least 8 GB of memory.

::: tip Docker memory is shared
The memory that you give Docker is shared between all running containers.
:::

You can adjust the memory that Docker makes available to containers in the Settings or Preferences menu of Docker Desktop. To find this menu, consult the User Manual for your version of Docker Desktop in the [Docker Desktop documentation](https://docs.docker.com/desktop/).


![](/orchestration/server/docker-memory-setting.png)

### Where to go next

The [Prefect Community Slack](https://prefect.io/slack) is a great place to ask for help! You can also write a new post in our [GitHub Discussion Board](https://github.com/PrefectHQ/prefect/discussions/new).

::: tip Save the output from `prefect server start`
If you ask for help, someone may ask to see the text that the `prefect server start` command generated when you ran it. Saving a copy of that text now will help speed up troubleshooting later!
:::