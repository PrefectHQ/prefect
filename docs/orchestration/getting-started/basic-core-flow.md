# Run a flow

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

Now that you have Prefect installed, you're ready to run a flow.

A [flow](/core/concepts/flows.html) is a container for [tasks](/core/concepts/tasks.html) and shows the direction of work and the dependencies between tasks.

To run your flow, paste the code below into an interactive Python REPL session: 

```python
import prefect
from prefect import task, Flow

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello world!")

with Flow("hello-flow") as flow:
    hello_task()

flow.run()
```

You should see the following logs after running `flow.run()` :

```
[2021-12-17 14:55:05-0500] INFO - prefect.FlowRunner | Beginning Flow run for 'hello-flow'
[2021-12-17 14:55:05-0500] INFO - prefect.TaskRunner | Task 'hello_task': Starting task run...
[2021-12-17 14:55:05-0500] INFO - prefect.hello_task | Hello world!
[2021-12-17 14:55:05-0500] INFO - prefect.TaskRunner | Task 'hello_task': Finished task run for task with final state: 'Success'
[2021-12-17 14:55:05-0500] INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded
<Success: "All reference tasks succeeded.">
```

You can also save this code to a file called `hello_flow.py` and run it from a terminal session:

```
$ python hello_flow.py
[2021-12-17 14:52:24-0500] INFO - prefect.FlowRunner | Beginning Flow run for 'hello-flow'
[2021-12-17 14:52:24-0500] INFO - prefect.TaskRunner | Task 'hello_task': Starting task run...
[2021-12-17 14:52:24-0500] INFO - prefect.hello_task | Hello world!
[2021-12-17 14:52:24-0500] INFO - prefect.TaskRunner | Task 'hello_task': Finished task run for task with final state: 'Success'
[2021-12-17 14:52:24-0500] INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded
```

If you're running into issues, check that your Python environment is properly set up to run Prefect. Refer to the [Prefect Core Installation](/core/getting_started/install.html) documentation for further details.

Now you're got a basic flow running locally, we can set up an API and UI using Prefect Cloud and register it. 