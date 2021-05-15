---
sidebarDepth: 2
editLink: false
---
# get
---
<h3>flows</h3>
  Query information regarding your Prefect flows.

  <pre><code>Options:<br>      --name, -n      TEXT    A flow name to query<br>      --version, -v   TEXT    A flow version to query<br>      --project, -p   TEXT    The name of a project to query<br>      --limit, -l     INTEGER A limit amount of flows to query, defaults to 10<br>      --all-versions          Output all versions of a flow, default shows most recent<br><br></code></pre><h3>tasks</h3>
  Query information regarding your Prefect tasks.

  <pre><code>Options:<br>      --name, -n          TEXT    A task name to query<br>      --flow-name, -fn    TEXT    A flow name to query<br>      --flow-version, -fv INTEGER A flow version to query<br>      --project, -p       TEXT    The name of a project to query<br>      --limit, -l         INTEGER A limit amount of tasks to query, defaults to 10<br><br></code></pre><h3>projects</h3>
  Query information regarding your Prefect projects.

  <pre><code>Options:<br>      --name, -n      TEXT    A project name to query<br><br></code></pre><h3>flow-runs</h3>
  Query information regarding Prefect flow runs.

  <pre><code>Options:<br>      --limit, l          INTEGER A limit amount of flow runs to query, defaults to 10<br>      --flow, -f          TEXT    Name of a flow to query for runs<br>      --project, -p       TEXT    Name of a project to query<br>      --started, -s               Only retrieve started flow runs, default shows `Scheduled` runs<br><br></code></pre><h3>logs</h3>
  Query logs for a flow run.

  Note: at least one of `name` or `id` must be specified. If only `name` is
  set then the most recent flow run with that name will be queried.

  <pre><code>Options:<br>      --name, -n      TEXT    A flow run name to query<br>      --id            TEXT    A flow run ID to query<br>      --info, -i              Retrieve detailed logging info<br><br></code></pre>
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>