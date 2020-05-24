---
sidebarDepth: 2
editLink: false
---
# Postgres Tasks
---
This module contains a collection of tasks for interacting with Postgres databases via
the psycopg2 library.
 ## PostgresExecute
 <div class='class-sig' id='prefect-tasks-postgres-postgres-postgresexecute'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.postgres.postgres.PostgresExecute</p>(db_name, user, password, host, port=5432, query=None, data=None, commit=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/postgres/postgres.py#L7">[source]</a></span></div>

Task for executing a query against a Postgres database.

**Args**:     <ul class="args"><li class="args">`db_name (str)`: name of Postgres database     </li><li class="args">`user (str)`: user name used to authenticate     </li><li class="args">`password (str)`: password used to authenticate     </li><li class="args">`host (str)`: database host address     </li><li class="args">`port (int, optional)`: port used to connect to Postgres database, defaults to 5432 if not provided     </li><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using placeholder is query string     </li><li class="args">`commit (bool, optional)`: set to True to commit transaction, defaults to false     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-postgres-postgres-postgresexecute-run'><p class="prefect-class">prefect.tasks.postgres.postgres.PostgresExecute.run</p>(query=None, data=None, commit=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/postgres/postgres.py#L46">[source]</a></span></div>
<p class="methods">Task run method. Executes a query against Postgres database.<br><br>**Args**:     <ul class="args"><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using         placeholder is query string     </li><li class="args">`commit (bool, optional)`: set to True to commit transaction, defaults to false</li></ul>**Returns**:     <ul class="args"><li class="args">None</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if query parameter is None or a blank string     </li><li class="args">`DatabaseError`: if exception occurs when executing the query</li></ul></p>|

---
<br>

 ## PostgresFetch
 <div class='class-sig' id='prefect-tasks-postgres-postgres-postgresfetch'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.postgres.postgres.PostgresFetch</p>(db_name, user, password, host, port=5432, fetch="one", fetch_count=10, query=None, data=None, commit=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/postgres/postgres.py#L95">[source]</a></span></div>

Task for fetching results of query from Postgres database.

**Args**:     <ul class="args"><li class="args">`db_name (str)`: name of Postgres database     </li><li class="args">`user (str)`: user name used to authenticate     </li><li class="args">`password (str)`: password used to authenticate     </li><li class="args">`host (str)`: database host address     </li><li class="args">`port (int, optional)`: port used to connect to Postgres database, defaults to 5432 if not provided     </li><li class="args">`fetch (str, optional)`: one of "one" "many" or "all", used to determine how many results to fetch from executed query     </li><li class="args">`fetch_count (int, optional)`: if fetch = 'many', determines the number of results to fetch, defaults to 10     </li><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using placeholder is query string     </li><li class="args">`commit (bool, optional)`: set to True to commit transaction, defaults to false     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor     </li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-postgres-postgres-postgresfetch-run'><p class="prefect-class">prefect.tasks.postgres.postgres.PostgresFetch.run</p>(fetch="one", fetch_count=10, query=None, data=None, commit=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/postgres/postgres.py#L140">[source]</a></span></div>
<p class="methods">Task run method. Executes a query against Postgres database and fetches results.<br><br>**Args**:     <ul class="args"><li class="args">`fetch (str, optional)`: one of "one" "many" or "all", used to determine how many results to fetch from executed query     </li><li class="args">`fetch_count (int, optional)`: if fetch = 'many', determines the number of results to fetch, defaults to 10     </li><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using placeholder is query string     </li><li class="args">`commit (bool, optional)`: set to True to commit transaction, defaults to false</li></ul>**Returns**:     <ul class="args"><li class="args">`records (tuple or list of tuples)`: records from provided query</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if query parameter is None or a blank string     </li><li class="args">`DatabaseError`: if exception occurs when executing the query</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on May 14, 2020 at 21:12 UTC</p>