import warnings
from airflow.models import DagBag
from collections import defaultdict
import os
import subprocess
import tempfile

import prefect
from prefect import Flow
from prefect.engine import signals
from prefect.tasks.shell import ShellTask


## TODO:
## - detect features to warn about such as XComms
## - launch UI?
## - trigger rules / retries

class AirTask(ShellTask):
    def __init__(self, task, **kwargs):
        name = task.task_id
        dag_id = task.dag_id
        tr = task.trigger_rule
        cmd = 'airflow run {0} {1} !execution_date'.format(dag_id, name)
        self.dag_id = dag_id
        super().__init__(name=name, command=cmd, **kwargs)

    def pre_check(self, execution_date, airflow_env):
        check_cmd = 'airflow task_state {0} {1} {2} | tail -1'.format(self.dag_id, self.name, execution_date)
        status = subprocess.check_output(['bash', '-c', check_cmd], env=airflow_env)
        if status.decode().rstrip() == 'skipped':
            raise signals.SKIP("Task marked as 'skipped' in airflow db")

    def post_check(self, execution_date, airflow_env):
        check_cmd = 'airflow task_state {0} {1} {2} | tail -1'.format(self.dag_id, self.name, execution_date)
        status = subprocess.check_output(['bash', '-c', check_cmd], env=airflow_env)
        if status.decode().rstrip() != 'success':
            raise signals.FAIL('Airflow task state was marked as {}'.format(status.decode().rstrip()))

    def run(self):
        execution_date = prefect.context.get('_execution_date')
        airflow_env = prefect.context.get('_airflow_env')
        self.pre_check(execution_date, airflow_env)
        self.command = self.command.replace('!execution_date', execution_date)
        res = super().run(env=airflow_env)
        self.post_check(execution_date, airflow_env)
        return res


class AirFlow(Flow):
    def __init__(self, dag_name, *args, **kwargs):
       self.dag = DagBag().dags[dag_name]
       super().__init__(*args, **kwargs)
       self.populate_tasks()

    def init_db(self):
        self.td = tempfile.TemporaryDirectory(prefix='prefect-airflow')
        env = os.environ.copy()
        env['AIRFLOW__CORE__SQL_ALCHEMY_CONN'] = 'sqlite:///' + self.td.name + '/prefect-airflow.db'
        status = subprocess.check_output(['bash', '-c', 'airflow initdb'], env=env)
        return env

    def run(self, execution_date, *args, **kwargs):
        env = self.init_db()
        with prefect.context(_execution_date=execution_date, _airflow_env=env):
            return super().run(*args, **kwargs)

    def issue_warnings(self, task):
        parameter_warning = False
        if task.params:
            warnings.warn("Use of Airflow parameters detected; consider converting these to Prefect Parameters.")
## pools too

    def populate_tasks(self):
        task_dict = {}

        def to_task(t):
            if t.task_id not in task_dict:
                task_dict[t.task_id] = AirTask(t)
            return task_dict[t.task_id]

        to_process = self.dag.roots # airflow roots are actually leaves...
        while to_process:
            airtask = to_process.pop()
            self.issue_warnings(airtask)
            self.set_dependencies(task=to_task(airtask),
                                  upstream_tasks=[to_task(t) for t in airtask.upstream_list])
            to_process += airtask.upstream_list


if __name__ == '__main__':
    flow = AirFlow('example_branch_operator')
    res = flow.run(return_tasks=flow.tasks, execution_date='2018-09-01')
