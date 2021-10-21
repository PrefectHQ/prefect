---
sidebarDepth: 2
editLink: false
---
# server
---
<h3>start</h3>
  This command spins up all infrastructure and services for the Prefect Core
  server

  <pre><code>Options:<br>      --version, -v       TEXT    The server image versions to use (for example, '0.1.0'<br>                                  or 'master'). Defaults to `core-a.b.c` where `a.b.c.`<br>                                  is the version of Prefect Core currently running.<br>      --ui-version, -uv   TEXT    The UI image version to use (for example, '0.1.0' or<br>                                  'master'). Defaults to `core-a.b.c` where `a.b.c.` is<br>                                  the version of Prefect Core currently running.<br>      --skip-pull                 Flag to skip pulling new images (if available)<br>      --no-upgrade, -n            Flag to avoid running a database upgrade when the<br>                                  database spins up<br>      --no-ui, -u                 Flag to avoid starting the UI<br><br>      --postgres-port     TEXT    Port used to serve Postgres, defaults to '5432'<br>      --hasura-port       TEXT    Port used to serve Hasura, defaults to '3000'<br>      --graphql-port      TEXT    Port used to serve the GraphQL API, defaults to '4201'<br>      --ui-port           TEXT    Port used to serve the UI, defaults to '8080'<br>      --server-port       TEXT    Port used to serve the Core server, defaults to '4200'<br><br>      --no-postgres-port          Disable port map of Postgres to host<br>      --no-hasura-port            Disable port map of Hasura to host<br>      --no-graphql-port           Disable port map of the GraphQL API to host<br>      --no-ui-port                Disable port map of the UI to host<br>      --no-server-port            Disable port map of the Core server to host<br><br>      --use-volume                Enable the use of a volume for the Postgres service<br>      --volume-path       TEXT    A path to use for the Postgres volume, defaults to<br>                                  '~/.prefect/pg_data'<br><br></code></pre><h3>create-tenant</h3>
  This command creates a tenant for the Prefect Server

  <pre><code>Options:<br>      --name, -n       TEXT    The name of a tenant to create<br>      --slug, -n       TEXT    The slug of a tenant to create<br><br></code></pre>
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>