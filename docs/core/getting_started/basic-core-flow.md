Below is a basic core flow that you can copy:

```python
import prefect
from prefect import task, Flow

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello world!")

flow = Flow("hello-flow", tasks=[hello_task])

flow.run()
```

Paste the code above into an interactive Python REPL session. You should see the following logs after running `flow.run()` :

```
[2020-01-08 23:49:00,239] INFO - prefect.FlowRunner | Beginning Flow run for 'hello-flow'
[2020-01-08 23:49:00,242] INFO - prefect.FlowRunner | Starting flow run.
[2020-01-08 23:49:00,249] INFO - prefect.TaskRunner | Task 'hello_task': Starting task run...
[2020-01-08 23:49:00,249] INFO - prefect.Task: hello_task | Hello world!
[2020-01-08 23:49:00,251] INFO - prefect.TaskRunner | Task 'hello_task': finished task run for task with final state: 'Success'
[2020-01-08 23:49:00,252] INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded
```

If you're running into issues, check that your Python environment is properly set up to run Prefect. Refer to the [Prefect Core Installation](https://docs.prefect.io/core/getting_started/installation.html) documentation for further details.

Now you're got a basic flow running, if you want to do more with Prefect you have many options.  To register your flow with our API, check out the [Orchestration Layer]() docs.  To find out more about Prefect Core Concepts, check out [Thinking Prefectly]().  There's also more advanced [tutorials]() or [video and blog resources]().