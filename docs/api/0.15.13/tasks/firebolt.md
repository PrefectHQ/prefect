---
sidebarDepth: 2
editLink: false
---
# Firebolt Tasks
---
This module contains a collection of tasks for interacting with Firebolt databases via
the firebolt-python-sdk library.
 ## FireboltQuery
 <div class='class-sig' id='prefect-tasks-firebolt-firebolt-fireboltquery'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.firebolt.firebolt.FireboltQuery</p>(database=None, username=None, password=None, engine_name=None, query=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/firebolt/firebolt.py#L7">[source]</a></span></div>

Task for executing a query against a Firebolt database.

**Args**:     <ul class="args"><li class="args">`database (str)`: name of the database to use.     </li><li class="args">`username (str)`: username used to authenticate.     </li><li class="args">`password (str)`: password used to authenticate.     </li><li class="args">`engine_name (str)`: name of the engine to use.     </li><li class="args">`query (str)`: query to execute against database.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task constructor.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-firebolt-firebolt-fireboltquery-run'><p class="prefect-class">prefect.tasks.firebolt.firebolt.FireboltQuery.run</p>(database=None, username=None, password=None, engine_name=None, query=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/firebolt/firebolt.py#L36">[source]</a></span></div>
<p class="methods">Task run method. Executes a query against Firebolt database.<br><br>**Args**:     <ul class="args"><li class="args">`database (str)`: name of the database to use.     </li><li class="args">`username (str)`: username used to authenticate.     </li><li class="args">`password (str)`: password used to authenticate.     </li><li class="args">`engine_name (str)`: name of the engine to use.     </li><li class="args">`query (str)`: query to execute against database.</li></ul> **Returns**:     <ul class="args"><li class="args">`List[List]`: output of 'cursor.fetchall()' if 'cursor.execute(query)' > 0,         else an empty list</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a required parameter is not supplied.     </li><li class="args">`DatabaseError`: if exception occurs when executing the query.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>