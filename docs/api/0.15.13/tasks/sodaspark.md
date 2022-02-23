---
sidebarDepth: 2
editLink: false
---
# SodaSpark Tasks
---
This module contains a collection of tasks to run Data Quality tests using soda-spark library
 ## SodaSparkScan
 <div class='class-sig' id='prefect-tasks-sodaspark-sodaspark-tasks-sodasparkscan'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.sodaspark.sodaspark_tasks.SodaSparkScan</p>(scan_def=None, df=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/sodaspark/sodaspark_tasks.py#L7">[source]</a></span></div>

Task for running a SodaSpark scan given a scan definition and a Spark Dataframe. For information about SodaSpark please refer to https://docs.soda.io/soda-spark/install-and-use.html. SodaSpark uses PySpark under the hood, hence you need Java to be installed on the machine where you run this task.

**Args**:     <ul class="args"><li class="args">`scan_def (str, optional)`: scan definition.       Can be either a path to a YAML file containing the scan definition.       Please refer to https://docs.soda.io/soda-sql/scan-yaml.html for more information.       or the scan definition given as a valid YAML string     </li><li class="args">`df (pyspark.sql.DataFrame, optional)`: Spark DataFrame.       DataFrame where to run tests defined in the scan definition.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-sodaspark-sodaspark-tasks-sodasparkscan-run'><p class="prefect-class">prefect.tasks.sodaspark.sodaspark_tasks.SodaSparkScan.run</p>(scan_def=None, df=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/sodaspark/sodaspark_tasks.py#L30">[source]</a></span></div>
<p class="methods">Task run method. Execute a scan against a Spark DataFrame.<br><br>**Args**:     <ul class="args"><li class="args">`scan_def (str, optional)`: scan definition.       Can be either a path to a YAML file containing the scan definition.       Please refer to https://docs.soda.io/soda-sql/scan-yaml.html for more information.       or the scan definition given as a valid YAML string     </li><li class="args">`df (pyspark.sql.DataFrame, optional)`: Spark DataFrame.       DataFrame where to run tests defined in the scan definition.</li></ul> **Returns**:     <ul class="args"></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>