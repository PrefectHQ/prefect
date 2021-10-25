---
sidebarDepth: 2
editLink: false
---
# Dremio Tasks
---
This module contains a collection of tasks for interacting with Dremio Query Engine via
the pyarrow library.
 ## DremioFetch
 <div class='class-sig' id='prefect-tasks-dremio-dremio-dremiofetch'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.dremio.dremio.DremioFetch</p>(user, password, host, port=32010, query=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dremio/dremio.py#L35">[source]</a></span></div>

Task for fetching results of a query using Dremio Query Engine.

**Args**:     <ul class="args"><li class="args">`user (str)`: user name used to authenticate     </li><li class="args">`password (str)`: password used to authenticate     </li><li class="args">`host (str)`: Dremio host address     </li><li class="args">`port (int, optional)`: port used to connect to FlightClient, defaults to 32010 if not         provided     </li><li class="args">`query (str, optional)`: query to execute against Dremio     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-dremio-dremio-dremiofetch-run'><p class="prefect-class">prefect.tasks.dremio.dremio.DremioFetch.run</p>(user, password, host, port, query)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dremio/dremio.py#L66">[source]</a></span></div>
<p class="methods">Task run method. Executes a query against Dremio and fetches results.<br><br>**Args**:     <ul class="args"><li class="args">`user (str)`: user name used to authenticate     </li><li class="args">`password (str)`: password used to authenticate     </li><li class="args">`host (str)`: Dremio host address     </li><li class="args">`port (int, optional)`: port used to connect to FlightClient, defaults to 32010 if not         provided     </li><li class="args">`query (str, optional)`: query to execute against query engine</li></ul> **Returns**:     <ul class="args"><li class="args">`dict`: a dictionary of data returned by Dremio</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if `query` is `None`</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>