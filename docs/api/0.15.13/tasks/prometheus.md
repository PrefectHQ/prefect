---
sidebarDepth: 2
editLink: false
---
# prometheus Tasks
---
Tasks for interacting with Prometheus. The main task are using pushgateway 
 ## PushGaugeToGateway
 <div class='class-sig' id='prefect-tasks-prometheus-pushgateway-pushgaugetogateway'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.prometheus.pushgateway.PushGaugeToGateway</p>(pushgateway_url=None, counter_name=None, counter_description=None, grouping_key=None, job_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/prometheus/pushgateway.py#L182">[source]</a></span></div>

Task that allow you to push a Gauge to prometheus [PushGateway] (https://prometheus.io/docs/practices/pushing/).This method is using the [prometheus_client](https://github.com/prometheus/client_python#exporting-to-a-pushgateway).

This is a push mode task that it will remove all previous items that match the grouping key.

Some of the main usage of that task is to allow to push inside of your workflow to prometheus like number of rows, quality of the values or anything you want to monitor.

**Args**:     <ul class="args"><li class="args">`pushgateway_url (str, optional)`: Url of the prometheus pushgateway instance     </li><li class="args">`counter_name (str, optional)`: Name of the counter     </li><li class="args">`counter_description (str, optional)`: description of the counter     </li><li class="args">`grouping_key (str, optional)`: List of the key used to calculate the grouping key     </li><li class="args">`job_name (str, optional)`: Name of the job     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>


---
<br>

 ## PushAddGaugeToGateway
 <div class='class-sig' id='prefect-tasks-prometheus-pushgateway-pushaddgaugetogateway'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.prometheus.pushgateway.PushAddGaugeToGateway</p>(pushgateway_url=None, counter_name=None, counter_description=None, grouping_key=None, job_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/prometheus/pushgateway.py#L226">[source]</a></span></div>

Task that allow you to push add a Gauge to prometheus [PushGateway] (https://prometheus.io/docs/practices/pushing/). This method is using the [prometheus_client](https://github.com/prometheus/client_python#exporting-to-a-pushgateway).

This is a push add mode task that will add value into the same grouping key.

Some of the main usage of that task is to allow to push inside of your workflow to prometheus like number of rows, quality of the values or anything you want to monitor.

**Args**:     <ul class="args"><li class="args">`pushgateway_url (str, optional)`: Url of the prometheus pushgateway instance     </li><li class="args">`counter_name (str, optional)`: Name of the counter     </li><li class="args">`counter_description (str, optional)`: description of the counter     </li><li class="args">`grouping_key (str, optional)`: List of the key used to calculate the grouping key     </li><li class="args">`job_name (str, optional)`: Name of the job     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>