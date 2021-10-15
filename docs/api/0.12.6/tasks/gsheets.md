---
sidebarDepth: 2
editLink: false
---
# Google Sheets Tasks
---
A collection of tasks for interacting with Google Sheets.
 ## WriteGsheetRow
 <div class='class-sig' id='prefect-tasks-gsheets-gsheets-writegsheetrow'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.gsheets.gsheets.WriteGsheetRow</p>(credentials_filename=None, sheet_key=None, worksheet_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/gsheets/gsheets.py#L8">[source]</a></span></div>

A task for writing a row to a Google Sheet. Note that _all_ initialization settings can be provided / overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`credentials_filename (Union[str, pathlib.Path])`: Location of credentials file     </li><li class="args">`sheet_key (str)`: The key corresponding to the Google Sheet     </li><li class="args">`worksheet_name (str)`: The worksheet to target     </li><li class="args">`**kwargs (optional)`: additional kwargs to pass to the `Task` constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-gsheets-gsheets-writegsheetrow-run'><p class="prefect-class">prefect.tasks.gsheets.gsheets.WriteGsheetRow.run</p>(data, credentials_filename=None, sheet_key=None, worksheet_name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/gsheets/gsheets.py#L32">[source]</a></span></div>
<p class="methods">Appends a row of data to a Google Sheets worksheet<br><br>**Args**:     <ul class="args"><li class="args">`data (list)`: the data to insert. This should be formatted as a list     </li><li class="args">`credentials_filename (Union[str, pathlib.Path])`: Location of credentials file     </li><li class="args">`sheet_key (str)`: The key corresponding to the Google Sheet     </li><li class="args">`worksheet_name (str)`: The worksheet to target</li></ul>**Returns**:     <ul class="args"><li class="args">a dictionary containing information about the successful insert</li></ul></p>|

---
<br>

 ## ReadGsheetRow
 <div class='class-sig' id='prefect-tasks-gsheets-gsheets-readgsheetrow'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.gsheets.gsheets.ReadGsheetRow</p>(credentials_filename=None, sheet_key=None, worksheet_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/gsheets/gsheets.py#L58">[source]</a></span></div>

A task for reading a row from a Google Sheet. Note that _all_ initialization settings can be provided / overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`credentials_filename (Union[str, pathlib.Path])`: Location of credentials file     </li><li class="args">`sheet_key (str)`: The key corresponding to the Google Sheet     </li><li class="args">`worksheet_name (str)`: The worksheet to target     </li><li class="args">`**kwargs (optional)`: additional kwargs to pass to the `Task` constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-gsheets-gsheets-readgsheetrow-run'><p class="prefect-class">prefect.tasks.gsheets.gsheets.ReadGsheetRow.run</p>(row, credentials_filename=None, sheet_key=None, worksheet_name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/gsheets/gsheets.py#L82">[source]</a></span></div>
<p class="methods">Appends a row of data to a Google Sheets worksheet<br><br>**Args**:     <ul class="args"><li class="args">`row (int)`: The number of the row to read     </li><li class="args">`credentials_filename (Union[str, pathlib.Path])`: Location of credentials file     </li><li class="args">`sheet_key (str)`: The key corresponding to the Google Sheet     </li><li class="args">`worksheet_name (str)`: The worksheet to target</li></ul>**Returns**:     <ul class="args"><li class="args">a list of values from the row</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>