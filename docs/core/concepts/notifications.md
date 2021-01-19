# Notifications and State Handlers

Alerts, notifications, and dynamically responding to task state are important features of any workflow tool. Using Prefect primitives, users can create Tasks that send notifications after certain tasks run or fail using Prefect's trigger logic. This will work, but does not cover more subtle uses of notification logic (e.g., receiving a notification if a task _retries_). For this reason, Prefect introduces a flexible concept called "state handlers", which can be attached to individual tasks or flows. At a high level, a state handler is a function that is called on every change of state for the underlying object; these can be used for sending alerts upon failure, emails upon success, or more nuanced handling based on the information contained in both the old and new states.

In addition to working with the `state_handler` API directly, Prefect provides higher level wrappers for implementing common use cases
such as failure callbacks.

::: tip Prefect States
State handlers are intimately connected with Prefect's concept of "State". We recommend reviewing [the concept doc on States](states.html) before reading further.
:::

## State Handlers

Let's start with the definition of a state handler:

```python
def state_handler(obj: Union[Task, Flow], old_state: State, new_state: State) -> Optional[State]:
    """
    Any function with this signature can serve as a state handler.

    Args:
        - obj (Union[Task, Flow]): the underlying object to which this state handler
            is attached
        - old_state (State): the previous state of this object
        - new_state (State): the proposed new state of this object

    Returns:
        - Optional[State]: the new state of this object (typically this is just `new_state`)
    """
    pass
```

As you can see, the state handler API is a simple way for executing arbitrary Python code with every state change.

A simple example will clarify its use:

```python
from prefect import Task, Flow


def my_state_handler(obj, old_state, new_state):
    msg = "\nCalling my custom state handler on {0}:\n{1} to {2}\n"
    print(msg.format(obj, old_state, new_state))
    return new_state


my_flow = Flow(name="state-handler-demo",
               tasks=[Task()],
               state_handlers=[my_state_handler])
my_flow.run()
```

Ignoring logs, this should output:

```
Calling my custom state handler on <Flow: name=state-handler-demo>:
Scheduled() to Running("Running flow.")

Calling my custom state handler on <Flow: name=state-handler-demo>:
Running("Running flow.") to Success("All reference tasks succeeded.")
```

In exactly the same way, we can attach this state handler to an individual task instead of the flow:

```python
t = Task(state_handlers=[my_state_handler])
flow = Flow(name="state-handler-demo", tasks=[t])
flow.run()
```

Once again ignoring logs, this should output:

```
Calling my custom state handler on <Task: Task>:
Pending() to Running("Starting task run.")

Calling my custom state handler on <Task: Task>:
Running("Starting task run.") to Success("Task run succeeded.")
```

At the end of the day, that's all there is to it! However, the simplicity of the API belies the many possible usage patterns for this feature, which is what we will look at next.

::: tip Note
For the sake of simplicity, for the rest of this document we will focus on _task_ state handlers, but everything we discuss applies equally to flows.
:::

## Sending a simple notification

As our above example demonstrated, it is very easy to intercept task states and respond to them. In fact, our previous example can be thought of as a simple notification system in which we print notifications to stdout. Let's take this one step further and write a notifier that posts an update to Slack whenever our task has finished its run. In order for this example to work, you'll need to have a Slack app setup with an [incoming webhook](https://api.slack.com/incoming-webhooks). If you don't use Slack or don't have an app, no worries - just swap out the Slack URL with any other webserver you might have access to.

```python
import requests
from prefect import Task, Flow
from prefect.client.secrets import Secret

def post_to_slack(task, old_state, new_state):
    if new_state.is_finished():
        msg = "Task {0} finished in state {1}".format(task, new_state)
        # replace with your Slack webhook URL secret name
        secret_slack = Secret("SLACK_WEBHOOK_URL_SECRET_NAME").get()

        requests.post(secret_slack, json={"text": msg})

    return new_state


t = Task(state_handlers=[post_to_slack])
flow = Flow(name="state-handler-demo", tasks=[t])
flow.run()
```

Here we are responding to state by only sending a notification when the task's state is considered "finished"; this includes `Success` states as well as `Failed` states, but does not include states such as `Retrying` or `Scheduled`.

::: warning Notification failure causes Task failure
We could have raised an error if the POST request returned a non-200 status code. This is fine, but be warned: Prefect considers state handlers an integral part of task execution, and consequently if an error is raised when calling a task's state handlers, the task run will be aborted and the task will be marked "Failed".
:::

::: tip Handlers can use Prefect Secrets
Most notification systems will require some form of authentication. Don't despair - state handlers can retrieve Prefect Secrets just like Tasks.  (See post_to_slack above for an example.)
:::

## Responding to State

Most of our examples so far inform the user if and when a task enters a certain state. Prefect State objects contain rich information, and allow us to get more creative than that! Let's revisit our `post_to_slack` notifier and have it alert us if the task enters a `Retrying` state, and how long we have to wait for the retry to occur:

```python
import requests
from prefect import Task, Flow


def post_to_slack(task, old_state, new_state):
    if new_state.is_retrying():
        msg = "Task {0} failed and is retrying at {1}".format(task, new_state.start_time)

        # replace URL with your Slack webhook URL
        requests.post("https://XXXXX", json={"text": msg})

    return new_state


t = Task(state_handlers=[post_to_slack])
flow = Flow(name="state-handler-demo", tasks=[t])
flow.run() # the notifier is never run
```

This uses the `start_time` attribute of `Retrying` states to alert the user with more useful information.

::: tip Think outside the box
Because Prefect allows tasks to return data, we can actually have our state handler respond based on the outputs of the task. Even more interesting,
_any_ Prefect State can carry data - this includes `Failed` states.
:::

Let's implement a task that has a special mode of failure; if this failure mode occurs, we want to be alerted immediately.

```python
from prefect import task, Flow
from prefect.engine import signals


def alert_on_special_failure(task, old_state, new_state):
    if new_state.is_failed():
        if getattr(new_state.result, "flag", False) is True:
            print("Special failure mode!  Send all the alerts!")
            print("a == b == {}".format(new_state.result.value))

    return new_state


@task(state_handlers=[alert_on_special_failure])
def mission_critical_task(a, b):
    if a == b:
        fail_signal = signals.FAIL("a equaled b!")
        fail_signal.flag = True
        fail_signal.value = a
        raise fail_signal
    else:
        return 1 / (b - a)


with Flow(name="state-inspection-handler") as flow:
    result = mission_critical_task(1, 1)

flow.run()
# Special failure mode!  Send all the alerts!
# a == b == 1
```

Note that we can reuse this pattern of attaching information to our `FAIL` signal across many tasks (and consequently reuse this state handler in other situations).

## Using Multiple handlers

You might have noticed that the `state_handlers` argument is plural and accepts a list. This is because Prefect allows you to attach as many state handlers to a task as you wish! This pattern is useful for composing state handlers with different use cases (e.g., a special handler for failure and another for retries). It is also useful if there is are certain critical circumstances you want to be alerted for -- you can implement many different and various state handlers to make sure you are alerted ASAP.

::: tip State handlers are called in order
If you choose to provide multiple state handlers to a task, note that they will be called in the order in which they are provided.
:::

## Higher level API

Prefect provides tools for creating state handlers from smaller, more modular pieces. In particular, the `callback_factory` helper utility located in `prefect.utilities.notifications` allows you to create state handlers from two simpler functions - one that implements an action, and another that performs a check (or filter) that determines when that action should occur. Let's re-implement our `post_to_slack` retry handler using this utility:

```python
from prefect.utilities.notifications import callback_factory


def send_post(task, state):
    msg = "Task {0} failed and is retrying at {1}".format(task, state.start_time)
    requests.post("https://XXXXX", json={"text": msg})

post_to_slack = callback_factory(send_post, lambda s: s.is_retrying())
```

You can check that this state handler has identical behavior to the first one we implemented. This factory method allows users to mix and match pieces of logic using a simple API.

An incredibly common check is whether or not the state is `Failed`. For this reason, Prefect provides an even higher level API for constructing on failure callbacks. In particular, given a function with signature

```python
def f(obj: Union[Task, Flow], state: State) -> None
```

one can use the `on_failure` keyword argument to both Tasks and Flows for automatically creating the appropriate state handler.
