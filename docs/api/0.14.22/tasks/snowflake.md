---
sidebarDepth: 2
editLink: false
---
# Snowflake Tasks
---
This module contains a collection of tasks for interacting with snowflake databases via
the snowflake-connector-python library.
 ## SnowflakeQuery
 <div class='class-sig' id='prefect-tasks-snowflake-snowflake-snowflakequery'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.snowflake.snowflake.SnowflakeQuery</p>(account, user, password=None, private_key=None, database=None, schema=None, role=None, warehouse=None, query=None, data=None, autocommit=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/snowflake/snowflake.py#L7">[source]</a></span></div>

Task for executing a query against a snowflake database.

**Args**:     <ul class="args"><li class="args">`account (str)`: snowflake account name, see snowflake connector          package documentation for details     </li><li class="args">`user (str)`: user name used to authenticate     </li><li class="args">`password (str, optional)`: password used to authenticate.         password or private_lkey must be present     </li><li class="args">`private_key (bytes, optional)`: pem to authenticate.         password or private_key must be present     </li><li class="args">`database (str, optional)`: name of the default database to use     </li><li class="args">`schema (int, optional)`: name of the default schema to use     </li><li class="args">`role (str, optional)`: name of the default role to use     </li><li class="args">`warehouse (str, optional)`: name of the default warehouse to use     </li><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using placeholder         is query string     </li><li class="args">`autocommit (bool, optional)`: set to True to autocommit, defaults to None, which         takes snowflake AUTOCOMMIT parameter     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-snowflake-snowflake-snowflakequery-run'><p class="prefect-class">prefect.tasks.snowflake.snowflake.SnowflakeQuery.run</p>(query=None, data=None, autocommit=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/snowflake/snowflake.py#L60">[source]</a></span></div>
<p class="methods">Task run method. Executes a query against snowflake database.<br><br>**Args**:     <ul class="args"><li class="args">`query (str, optional)`: query to execute against database     </li><li class="args">`data (tuple, optional)`: values to use in query, must be specified using         placeholder is query string     </li><li class="args">`autocommit (bool, optional)`: set to True to autocommit, defaults to None         which takes the snowflake AUTOCOMMIT parameter</li></ul> **Returns**:     <ul class="args"><li class="args">None</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if query parameter is None or a blank string     </li><li class="args">`DatabaseError`: if exception occurs when executing the query</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>