---
sidebarDepth: 2
editLink: false
---
# register
---
<h3>flow</h3>
  Register a flow from a file. This call will pull a Flow object out of a
  `.py` file and call `flow.register` on it.

  <pre><code>Options:<br>      --file, -f      TEXT    The path to a local file which contains a flow  [required]<br>      --name, -n      TEXT    The `flow.name` to pull out of the file provided. If a name<br>                              is not provided then the first flow object found will be registered.<br>      --project, -p   TEXT    The name of a Prefect project to register this flow<br>      --label, -l     TEXT    A label to set on the flow, extending any existing labels.<br>                              Multiple labels are supported, eg. `-l label1 -l label2`.<br><br>  Examples:<br>      $ prefect register flow --file my_flow.py --name My-Flow -l label1 -l label2<br><br></code></pre>
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>