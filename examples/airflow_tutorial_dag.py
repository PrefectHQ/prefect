# rewrite of https://airflow.apache.org/tutorial.html

from datetime import datetime, timedelta

import prefect
from prefect import Flow, Parameter, task
from prefect.schedules import IntervalSchedule
from prefect.tasks.shell import ShellTask
from prefect.tasks.templates.jinja2 import JinjaTemplate

## default config settings such as this can generally be set in your
## user config file
retry_delay = timedelta(minutes=5)

## create all relevant tasks
t1 = ShellTask(
    name="print_date", command="date", max_retries=1, retry_delay=retry_delay
)
t2 = ShellTask(name="sleep", command="sleep 5", max_retries=3, retry_delay=retry_delay)


@task(max_retries=1, retry_delay=retry_delay)
def add_7():
    date = prefect.context.get("scheduled_start_time", datetime.utcnow())
    return date + timedelta(days=7)


## templated command; template vars will be read from both prefect.context as well as
## any passed kwargs to the task
command = """
    {% for i in range(5) %}
        echo "{{ scheduled_start_time }}"
        echo "{{ scheduled_start_time_7 }}"
        echo "{{ my_param }}"
    {% endfor %}
"""
templated_command = JinjaTemplate(
    template=command, max_retries=1, retry_delay=retry_delay
)

## create schedule for the Flow
schedule = IntervalSchedule(start_date=datetime(2015, 6, 1), interval=timedelta(days=1))

## create Flow and specify dependencies using functional API
## we don't actually attach the schedule to this Flow so it only runs once
with Flow("tutorial") as flow:
    my_param = Parameter("my_param")
    t2(upstream_tasks=[t1])
    t3 = templated_command(
        scheduled_start_time_7=add_7, my_param=my_param, upstream_tasks=[t1]
    )


flow.run(parameters={"my_param": "Parameter I passed in"})
