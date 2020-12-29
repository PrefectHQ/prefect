---
sidebarDepth: 2
editLink: false
---
# describe
---
<h3>flows</h3>
  Describe a Prefect flow.

  <pre><code>Options:<br>      --name, -n      TEXT    A flow name to query                [required]<br>      --version, -v   INTEGER A flow version to query<br>      --project, -p   TEXT    The name of a project to query<br>      --output, -o    TEXT    Output format, one of {'json', 'yaml'}.<br>                              Defaults to json.<br><br></code></pre><h3>tasks</h3>
  Describe tasks from a Prefect flow. This command is similar to `prefect
  describe flow` but instead of flow metadata it outputs task metadata.

  <pre><code>Options:<br>      --name, -n      TEXT    A flow name to query                [required]<br>      --version, -v   INTEGER A flow version to query<br>      --project, -p   TEXT    The name of a project to query<br>      --output, -o    TEXT    Output format, one of {'json', 'yaml'}.<br>                              Defaults to json.<br><br></code></pre><h3>flow-runs</h3>
  Describe a Prefect flow run.

  <pre><code>Options:<br>      --name, -n          TEXT    A flow run name to query            [required]<br>      --flow-name, -fn    TEXT    A flow name to query<br>      --output, -o        TEXT    Output format, one of {'json', 'yaml'}.<br>                                  Defaults to json.<br><br></code></pre>
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>