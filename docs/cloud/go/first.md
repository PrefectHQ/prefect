# First Cloud Flow

[[toc]]

## Write Flow

For this demonstration you may use any Flow you want but as an example here's Prefect's _Hello World_ ETL Flow:

```python
from prefect import task, Flow


@task
def extract():
    """Get a list of data"""
    return [1, 2, 3]


@task
def transform(data):
    """Multiply the input by 10"""
    return [i * 10 for i in data]


@task
def load(data):
    """Print the data to indicate it was received"""
    print("Here's your data: {}".format(data))


with Flow("ETL") as flow:
    e = extract()
    t = transform(e)
    l = load(t)
```

Now that you have a Flow you can run it locally with the `flow.run()` function. This is an entirely local run which does not use any of Prefect Cloud's features but you can easily change that by registering your Flow with Prefect Cloud!

## Register Flow with Prefect Cloud

In order to start taking advantage of Prefect Cloud for your Flow deployments you must _register_ that Flow. This is a step in which a Flow's metadata is sent to Prefect Cloud in order to support orchestration for that Flow.

:::tip Flow Code
**Note**: no actual code from the Flow is sent to Prefect Cloud. Only metadata about the existence and format of the Flow are received. All of your code is safe, secure, and private in your own infrastructure!
:::

In the same process where your Flow is defined, all you need to do to register your Flow is call `flow.register()` with the name of your desired Prefect Cloud project. Using the Flow above and the _Demo_ project created in the previous [Create a Project](/cloud/go/configure.html#create-a-project) step it would look something like this:

```python
flow.register(project_name="Demo")
```

You should see some output with a UUID that corresponds to your Flow in Prefect Cloud. If you do not then make sure you have [logged in to Prefect Cloud](/cloud/go/configure.html#log-in-to-prefect-cloud).

## Run Flow w/ Prefect Cloud

After your Flow has been registered with Prefect Cloud you can now run it and start utilizing its features! In the same process where your Flow is defined you can start a [Local Agent](/cloud/agent/local.html) which will be responsible for watching for Flow Runs that are scheduled in Prefect Cloud and deploy them accordingly. No need to go too in depth with Agents just yet, it will be addressed in a later document, but for now it helps to be aware that your Flow was registered by default with [Local Storage]() and thus will be deployed using a [Local Agent](/cloud/agent/local.html).

To start a Local Agent in process use the `flow.run_agent()` function:

```python
flow.run_agent()
```

You should see output similar to the logs below.

```
 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-12-01 10:46:33,169 - agent - INFO - Starting LocalAgent with labels {'your-machine.localdomain'}
2019-12-01 10:46:33,170 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-12-01 10:46:33,276 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-12-01 10:46:33,277 - agent - INFO - Waiting for flow runs...
```

Now that you have a Local Agent running it will remain there and periodically poll Prefect Cloud for scheduled runs that it needs to deploy. You can now schedule runs for this Flow! To create a Flow Run you have a few options at your disposal:

- Open another command line session and run `prefect run cloud --name ETL --project Demo`
- Navigate to the UI and click _Run_ on your Flow's page
- Use another method listed on the [Flow Runs](/cloud/concepts/flow_runs.html#flow-runs) doc

Once you run your Flow you should see logs from your Local Agent notifying you that it had found a Flow Run and submitted it for execution.

```
2019-12-01 10:47:11,831 - agent - INFO - Found 1 flow run(s) to submit for execution.
2019-12-01 10:47:12,365 - agent - INFO - Deploying flow run 4440a71f-6444-4bcd-bc14-1aa50e53df6c
2019-12-01 10:47:12,375 - agent - INFO - Submitted 1 flow run(s) for execution.
```

You should immediately be able to see the result of your Flow Run in the UI or through the CLI command `prefect get flow-runs`. If everything looks correct it is time to move forward and learn more about the building blocks of Flow deployment with Prefect Cloud!
