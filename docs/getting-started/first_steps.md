Set up your environment for Prefect workflow development.

1. Install Prefect
1. Run a Hello World Flow
1. Connect to Prefect's Orchestration API

### Install Prefect

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed instructions.

### Hello Prefect: Run a Flow

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

To define Prefect flows, you import our core library and add decorators, as shown in the above example. For the actual *orchestration* and *execution* of these workflows Prefect offers a dedicated orchestration API that is required for scheduling and viewing metadata.

### Prefect Cloud

To connect to Prefect's API, sign up for a forever free **[Prefect Cloud Account](https://app.prefect.cloud/).** 

Sign in or register a Prefect Cloud account and **[follow this guide to create your first Prefect workspace](/cloud/cloud-quickstart.md).**

Use the `prefect cloud login` Prefect CLI command to log into Prefect Cloud from your environment.

<div class="terminal">
```bash
$ prefect cloud login
```
</div>

The `prefect cloud login` command, used on its own, provides an interactive login experience. Using this command, you may log in with either an API key or through a browser.

<div class="terminal">
```shell
$ prefect cloud login
? How would you like to authenticate? [Use arrows to move; enter to select]
> Log in with a web browser
  Paste an API key
Opening browser...
Waiting for response...
? Which workspace would you like to use? [Use arrows to move; enter to select]
> prefect/terry-prefect-workspace
  g-gadflow/g-workspace
Authenticated with Prefect Cloud! Using workspace 'prefect/terry-prefect-workspace'.
```
</div>

If you choose to log in via the browser, Prefect opens a new tab in your default browser and enables you to log in and authenticate the session. Use the same login information as you originally used to create your Prefect Cloud account.


### Prefect server

Alternatively, to [host your own server](/host/index/) with a subset of Prefect Cloud's features, run the following command in the same environment, but in a separate terminal window:

```bash
prefect server start
```

## Next Steps

You're now ready to dive in and learn Prefect! 

Start with the [tutorial](/tutorial/) for an introduction to Prefect's core components and then checkout out the [concepts](/concepts/index/) for more in depth information.

Alternatively, to deploy a flow in as few steps as possible, check out our [deployment quickstart](/getting-started/deployment_quickstart/).
