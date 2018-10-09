import datetime as dt

import airflow
from airflow.models import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.trigger_rule import TriggerRule

dag = DAG(
    dag_id="trigger_rules",
    schedule_interval=dt.timedelta(hours=4),
    start_date=airflow.utils.dates.days_ago(2),
)

task1 = DummyOperator(task_id="task1", dag=dag)
task2 = DummyOperator(task_id="task2", dag=dag)
task3 = DummyOperator(task_id="task3", dag=dag, trigger_rule=TriggerRule.ONE_FAILED)
task3.set_upstream([task1, task2])
