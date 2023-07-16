Set up your environment for Prefect workflow development.

1. Install Prefect
1. Run a Hello World Flow
1. Connect to Prefect's Orchestration API

### Install Prefect

Install Prefect with 

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed instructions.

### Run a Hello World Flow

Import `flow` and decorate your Python function using the [`@flow`][prefect.flows.flow] decorator.

```python hl_lines="1 3"
from prefect import flow

@flow
def my_favorite_function():

    print("What is your favorite number?")
    return 42

print(my_favorite_function())
```

Thats it! Your function is now a flow. Run the code as you normally would, and you'll see its execution via the Prefect logs:

<div class="terminal">
```bash
$ python hello_prefect.py
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
What is your favorite number?
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed()
42
```
</div>

Prefect automatically persists all executions of your flow along with useful metadata such as start time, end time, and state. This is just the beginning, so keep exploring to learn how to add retries, notifications, scheduling and much more!

## Connect to Prefect's API

To define Prefect flows, you import our core library and add decorators, as shown in the above example. For the actual *orchestration* and *execution* of these workflows Prefect offers a dedicated orchestration API.

### Prefect Cloud

To connect to Prefect's API, sign up for a forever free [Prefect Cloud Account](https://app.prefect.cloud/). 

Sign in or register a Prefect Cloud account and [create your first Prefect workspace](/cloud/cloud-quickstart.md).

```bash
prefect cloud login
```

### Prefect server

Alternatively, to host your own server with a subset of Prefect Cloud's features, run the following command in the same environment, but in a separate terminal window:

```bash
prefect server start
```
