---
sidebarDepth: 0
---

# Resume flow at failure 

The following flow fails at run-time due to a `ZeroDivisionError` in the `failure` task

```python
from time import sleep

import prefect
from prefect import Flow, task
from prefect.engine import FlowRunner

@task
def i_will_take_forever() -> int:
    sleep(3)
    return 42


@task
def failure(a_number: int):
    return a_number / 0


def get_flow() -> Flow:
    
    with Flow("Success/Failure") as flow:

        a_great_number = i_will_take_forever()
        failure(a_great_number)
    
    return flow
```

Running this flow in an `iPython` command shell fails

```python
In[1]: run example.py
In[2]: flow = get_flow()
In[3]: flow.run()
```

Replacing `1/0` with `1/1` in `failure()` would fix this error, however, rerunning the whole flow including the slow `i_will_take_forever` is unncessary.  

```python
In[1]: run example.py
In[2]: from prefect.engine.state import Success
In[3]: long_task = flow.get_tasks(name="i_will_take_forever")[0]
In[4]: task_states =  {long_task : Success("Mocked success", result=42)}
In[5]: flow.run(task_states=task_states)
```

As a result the flow skips the slow task and resumes from failure.