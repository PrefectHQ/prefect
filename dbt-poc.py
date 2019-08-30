from prefect import task, Flow
from prefect.tasks.shell import ShellTask


task_run = ShellTask()

@task
def output_results(command):
    print(command)


with Flow("My first flow!") as flow:
    command = task_run()
    output_results(command)

status = flow.run()
