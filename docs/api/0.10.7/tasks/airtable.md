---
sidebarDepth: 2
editLink: false
---
# Airtable Tasks
---
A collection of tasks for interacting with Airtable.
 ## WriteAirtableRow
 <div class='class-sig' id='prefect-tasks-airtable-airtable-writeairtablerow'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.airtable.airtable.WriteAirtableRow</p>(base_key=None, table_name=None, credentials_secret=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airtable/airtable.py#L11">[source]</a></span></div>

A task for writing a row to an Airtable table.

Note that _all_ initialization settings can be provided / overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`base_key (str)`: the Airtable base key     </li><li class="args">`table_name (str)`: the table name     </li><li class="args">`credentials_secret (str, DEPRECATED)`: the name of a secret that contains an Airtable API key.     </li><li class="args">`**kwargs (optional)`: additional kwargs to pass to the `Task` constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-airtable-airtable-writeairtablerow-run'><p class="prefect-class">prefect.tasks.airtable.airtable.WriteAirtableRow.run</p>(data, base_key=None, table_name=None, api_key=None, credentials_secret=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airtable/airtable.py#L36">[source]</a></span></div>
<p class="methods">Inserts data into an Airtable table<br><br>**Args**:     <ul class="args"><li class="args">`data (dict)`: the data to insert. This should be formatted as a dictionary mapping         each column name to a value.     </li><li class="args">`base_key (str)`: the Airtable base key     </li><li class="args">`table_name (str)`: the table name     </li><li class="args">`api_key (str)`: an Airtable API key. This can be provided via a Prefect Secret     </li><li class="args">`credentials_secret (str, DEPRECATED)`: the name of a secret that contains an Airtable API key.</li></ul>**Returns**:     <ul class="args"><li class="args">a dictionary containing information about the successful insert</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on May 14, 2020 at 21:12 UTC</p>