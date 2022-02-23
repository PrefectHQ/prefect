---
sidebarDepth: 2
editLink: false
---
# SodaSQL Tasks
---
This module contains a collection of tasks to run Data Quality tests using soda-sql library
 ## SodaSQLScan
 <div class='class-sig' id='prefect-tasks-sodasql-sodasql-tasks-sodasqlscan'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.sodasql.sodasql_tasks.SodaSQLScan</p>(scan_def=None, warehouse_def=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/sodasql/sodasql_tasks.py#L9">[source]</a></span></div>

Task for running a SodaSQL scan given a scan definition and a warehouse definition.

**Args**:     <ul class="args"><li class="args">`scan_def (dict, str, optional)`: scan definition.         Can be either a path a SodaSQL Scan YAML file or a dictionary.         For more information regarding SodaSQL Scan YAML files         refer to https://docs.soda.io/soda-sql/documentation/scan.html     </li><li class="args">`warehouse_def (dict, str, optional)`: warehouse definition.         Can be either a path to a SodaSQL Warehouse YAML file or a dictionary.         For more information regarding SodaSQL Warehouse YAML files         refer to https://docs.soda.io/soda-sql/documentation/warehouse.html     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-sodasql-sodasql-tasks-sodasqlscan-run'><p class="prefect-class">prefect.tasks.sodasql.sodasql_tasks.SodaSQLScan.run</p>(scan_def=None, warehouse_def=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/sodasql/sodasql_tasks.py#L70">[source]</a></span></div>
<p class="methods">Task run method. Execute a Scan against a Scan definition using a Warehouse definition.<br><br>**Args**:     <ul class="args"><li class="args">`scan_def (dict, str, optional)`: scan definition.         Can be either a path a SodaSQL Scan YAML file or a dictionary.         For more information regarding SodaSQL Scan YAML files         refer to https://docs.soda.io/soda-sql/documentation/scan.html     </li><li class="args">`warehouse_def (dict, str, optional)`: warehouse definition.         Can be either a path to a SodaSQL Warehouse YAML file or a dictionary.         For more information regarding SodaSQL Warehouse YAML files         refer to https://docs.soda.io/soda-sql/documentation/warehouse.html</li></ul> **Returns**:     <ul class="args"></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if either scan_def or warehouse_def are None</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>