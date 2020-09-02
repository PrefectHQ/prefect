import pandas as pd
from prefect import task, Flow

task_func = task(lambda: pd.DataFrame())
undecorated_func = lambda x: x.rename("blah")

with Flow(name="Broken Flow") as flow:
    task_arg = task_func()
    undecorated_func(task_arg)