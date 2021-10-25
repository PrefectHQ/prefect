---
sidebarDepth: 2
editLink: false
---
# SQLite Tasks
---
 ## SQLiteQuery
 <div class='class-sig' id='prefect-tasks-database-sqlite-sqlitequery'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.database.sqlite.SQLiteQuery</p>(db=None, query=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/database/sqlite.py#L9">[source]</a></span></div>

Task for executing a single query against a sqlite3 database; returns the result (if any) from the query.

**Args**:     <ul class="args"><li class="args">`db (str, optional)`: the location of the database (.db) file     </li><li class="args">`query (str, optional)`: the optional _default_ query to execute at runtime;         can also be provided as a keyword to `run`, which takes precedence over this default.         Note that a query should consist of a _single SQL statement_.     </li><li class="args">`**kwargs (optional)`: additional keyword arguments to pass to the         standard Task initalization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-database-sqlite-sqlitequery-run'><p class="prefect-class">prefect.tasks.database.sqlite.SQLiteQuery.run</p>(db=None, query=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/database/sqlite.py#L28">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`db (str, optional)`: the location of the database (.db) file;         if not provided, `self.db` will be used instead.     </li><li class="args">`query (str, optional)`: the optional query to execute at runtime;         if not provided, `self.query` will be used instead. Note that a         query should consist of a _single SQL statement_.</li></ul> **Returns**:     <ul class="args"><li class="args">`[Any]`: the results of the query</li></ul></p>|

---
<br>

 ## SQLiteScript
 <div class='class-sig' id='prefect-tasks-database-sqlite-sqlitescript'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.database.sqlite.SQLiteScript</p>(db=None, script=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/database/sqlite.py#L51">[source]</a></span></div>

Task for executing a SQL script against a sqlite3 database.

**Args**:     <ul class="args"><li class="args">`db (str, optional)`: the location of the database (.db) file     </li><li class="args">`script (str, optional)`: the optional _default_ script string to render at runtime;         can also be provided as a keyword to `run`, which takes precedence over this default.     </li><li class="args">`**kwargs (optional)`: additional keyword arguments to pass to the         standard Task initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-database-sqlite-sqlitescript-run'><p class="prefect-class">prefect.tasks.database.sqlite.SQLiteScript.run</p>(db=None, script=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/database/sqlite.py#L68">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`db (str, optional)`: the location of the database (.db) file;         if not provided, `self.db` will be used instead.     </li><li class="args">`script (str, optional)`: the optional script to execute at runtime;         if not provided, `self.script` will be used instead.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>