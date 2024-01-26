---
description: Learn how to create interactive workflows with Prefect.
tags:
    - flow run
    - pause
    - suspend
    - input
    - human-in-the-loop workflows
    - interactive workflows
search:
  boost: 2
---

# Creating Interactive Workflows

!!! warning "Experimental"

    Flow interactivity is an experimental feature. The interface or behavior of this feature may change without warning in future releases.

    If you encounter any issues, please let us know in [Slack](https://www.prefect.io/slack/) or with a [Github](https://github.com/PrefectHQ/prefect) issue.

Flows can now pause or suspend execution and automatically resume when they receive type-checked input in Prefect's UI. Flows can also send and receive type-checked input at any time while running, without pausing or suspending. This guide will show you how to use these features to build _interactive workflows_.

## Pausing or suspending a flow until it receives input

You can pause or suspend a flow until it receives input from a user in Prefect's UI. This is useful when you need to ask for additional information or feedback before resuming a flow. Such workflows are often called [human-in-the-loop](https://hai.stanford.edu/news/humans-loop-design-interactive-ai-systems) (HITL) systems.

!!! note "What is human-in-the-loop interactivity used for?"

    Approval workflows that pause to ask a human to confirm whether a workflow should continue are very common in the business world. Certain types of [machine learning training](https://link.springer.com/article/10.1007/s10462-022-10246-w) and artificial intelligence workflows benefit from incorporating HITL design.

### Waiting for input

To receive input while paused or suspended you must use the `wait_for_input` parameter in the `pause_flow_run` or `suspend_flow_run` functions. This parameter accepts one of the following:

- A type like `int` or `str`
- A `pydantic.BaseModel` subclass
- A subclass of `prefect.input.RunInput`

The simplest way to pause or suspend and wait for input is to pass a type:

```python
from prefect import flow, pause_flow_run

@flow
async def greet_user():
    logger = get_run_logger()

    user_input = await pause_flow_run(wait_for_input=str)

    logger.info(f"Hello, {user_input.name}!")
```

In this example, the flow run will pause until a user clicks the Resume button in the Prefect UI, enters a name, and submits the form.

!!! note "What types can you pass for `wait_for_input`?"

    When you pass a type like `int` as an argument for the `wait_for_input` parameter to `pause_flow_run` or `suspend_flow_run`, Prefect automatically creates a Pydantic model containing one field annotated with the type you specified. This means you can use [any type annotation that Pydantic accepts](https://docs.pydantic.dev/1.10/usage/types/) as a field.

Instead of a basic type, you can pass in a `pydantic.BaseModel` class. This is useful if you already have `BaseModels` you want to use:

```python
from prefect import flow, pause_flow_run
from pydantic import BaseModel


class User(BaseModel):
    name: str
    age: int


@flow
async def greet_user():
    logger = get_run_logger()

    user = await pause_flow_run(wait_for_input=User)

    logger.info(f"Hello, {user.name}!")
```

!!! note "`BaseModel` subclasses are upgraded to `RunInput` subclasses automatically"

    When you pass a `pydantic.BaseModel` subclass as the `wait_for_input` argument to `pause_flow_run` or `suspend_flow_run`, Prefect automatically creates a `RunInput` class with the same behavior as your `BaseModel` and uses that instead.

    `RunInput` subclasses contain extra logic that allows Prefect to send them to flow runs and receive them from flow runs at runtime. You shouldn't notice any difference!

Finally, for advanced use cases like overriding how Prefect stores flow run inputs, you can create a `RunInput` subclass to use as the `wait_for_input` argument to `pause_flow_run` or `suspend_flow_run`.

```python
from prefect.input import RunInput

class UserInput(RunInput):
    name: str
    age: int
```

### Providing initial data

You can set default values for fields in your model by using the `with_initial_data` method. This is useful when you want to provide default values for the fields in your own `RunInput` subclasses.

Expanding on the example above, you could default the `name` field to "anonymous."

```python
from prefect.input import RunInput

class UserInput(RunInput):
    name: str
    age: int

@flow
async def greet_user():
    logger = get_run_logger()

    user_input = await pause_flow_run(
        wait_for_input=UserInput.with_initial_data(name="anonymous")
    )

    if user_input.name == "anonymous":
        logger.info("Hello, stranger!")
    else:
        logger.info(f"Hello, {user_input.name}!")
```

### Handling custom validation

Prefect uses the fields and type hints on your `RunInput` or `BaseModel` subclass to validate the general structure of input your flow run receives, but you might require more complex validation. If you do, you can use Pydantic [validators](https://docs.pydantic.dev/1.10/usage/validators/).

!!! warning "Custom validation runs after the flow run resumes"
Prefect transforms the type annotations in your `RunInput` or `BaseModel` class to a JSON schema and uses that schema in the UI for client-side validation. However, custom validation requires running logic defined in your `RunInput` class. Validation happens _after the flow resumes_, so you'll probably want to handle it explicitly in your flow. Continue reading for an example best practice.

The following is an example `RunInput` class that uses a custom field validator:

```python
import pydantic
from prefect.input import RunInput


class ShirtOrder(RunInput):
    size: Literal["small", "medium", "large", "xlarge"]
    color: Literal["red", "green", "black"]

    @pydantic.validator("color")
    def validate_age(cls, value, values, **kwargs):
        if value == "green" and values["size"] == "small":
            raise ValueError("Green is only in-stock for medium, large, and XL sizes.")

        return value
```

In the example, we use Pydantic's `validator` decorator to define a custom validation method for the `color` field. We can use it in a flow like this:

```python
import pydantic
from prefect import flow, pause_flow_run
from prefect.input import RunInput


class ShirtOrder(RunInput):
    size: Literal["small", "medium", "large", "xlarge"]
    color: Literal["red", "green", "black"]

    @pydantic.validator("color")
    def validate_age(cls, value, values, **kwargs):
        if value == "green" and values["size"] == "small":
            raise ValueError("Green is only in-stock for medium, large, and XL sizes.")

        return value


@flow
def get_shirt_order():
    shirt_order = pause_flow_run(wait_for_input=ShirtOrder)
```

If a user chooses any size and color combination other than `small` and `green`, the flow run will resume successfully. However, if the user chooses size `small` and color `green`, the flow run will resume, and `pause_flow_run` will raise a `ValidationError` exception. This will cause the flow run to fail and log the error.

However, what if you don't want the flow run to fail? One way to handle this case is to use a `while` loop and pause again if the `ValidationError` exception is raised:

```python
from typing import Literal

import pydantic
from prefect import flow, get_run_logger, pause_flow_run
from prefect.input import RunInput


class ShirtOrder(RunInput):
    size: Literal["small", "medium", "large", "xlarge"]
    color: Literal["red", "green", "black"]

    @pydantic.validator("color")
    def validate_age(cls, value, values, **kwargs):
        if value == "green" and values["size"] == "small":
            raise ValueError("Green is only in-stock for medium, large, and XL sizes.")

        return value


@flow
def get_shirt_order():
    logger = get_run_logger()
    shirt_order = None

    while shirt_order is None:
        try:
            shirt_order = pause_flow_run(wait_for_input=ShirtOrder)
        except pydantic.ValidationError as exc:
            logger.error(f"Invalid size and color combination: {exc}")

    logger.info(f"Shirt order: {shirt_order.size}, {shirt_order.color}")
```

This code will cause the flow run to continually pause until the user enters a valid age.

As an additional step, you may want to use an [automation](/concepts/automations) or [notification](/concepts/notifications/) to alert the user to the error.

## Sending and receiving input at runtime

Use the `send_input` and `receive_input` functions to send input to a flow run or receive input from a flow run at runtime. You don't need to pause or suspend the flow run to send or receive input.

!!! note "Why would you send or receive input without pausing or suspending?"

    You might want to send or receive input without pausing or suspending in scenarios where the flow run is designed to handle real-time data. For instance, in a live monitoring system, you might need to update certain parameters based on the incoming data without interrupting the flow. Another use is having a long-running flow that continually responds to runtime input with low latency. For example, if you're building a chatbot, you could have a flow that starts a GPT Assistant and manages a conversation thread.

The most important parameter to the `send_input` and `receive_input` functions is `run_type`, which should one of the following:

- A type like `int` or `str`
- A `pydantic.BaseModel` subclass
- A subclass of `prefect.input.RunInput`

Let's look at some examples! We'll check out `receive_input` first, followed by `send_input`, and then we'll see the two functions working together.

### Receiving input

The following flow uses `receive_input` to continually receive names and print a personalized greeting for each name it receives:

```python
from prefect import flow
from prefect.input.run_input import receive_input


@flow
async def greeter_flow():
    async for name_input in receive_input(str, timeout=None):
        print(f"Hello, {name_input}!")  # Prints "Hello, andrew!" if flow received "andrew"
```

When you pass a type like `str` into `receive_input`, Prefect creates a `RunInput` class to manage your input automatically. When your flow receives input of this type, Prefect uses this `RunInput` class to validate the input, and if validation succeeds, your flow sees the input in the type you specified. So in this example, if the flow received a valid string as input, the variable `name_input` contains the string.

If, instead, you specify a `BaseModel`, Prefect upgrades your `BaseModel` to a `RunInput` class, and the variable your flow sees -- in this case, `name_input` -- is a `RunInput` instance. Of course, if you pass in a `RunInput` class, no upgrade is needed, and you'll get a `RunInput` instance.

If you prefer to keep things simple and pass types like `str` into `receive_input`, you need access to the generated `RunInput` instance, pass `with_metadata=True` to `receive_input`:

```python
from prefect import flow
from prefect.input.run_input import receive_input


@flow
async def greeter_flow():
    async for name_input in receive_input(str, timeout=None, with_metadata=True):
        print(f"Hello, {name_input.value}!")

```

Notice that we are now printing `name_input.value`. When Prefect generates a `RunInput` for you from a basic type, the `RunInput` class has a single field, `value`, that uses a type annotation matching the type you specified. So if you call `receive_input` like this: `receive_input(str, with_metadata=True)`, that's equivalent to manually creating the following `RunInput` class and `receive_input` call:

```python
from prefect import flow
from prefect.input.run_input import RunInput

class GreeterInput(RunInput):
    value: str

@flow
async def greeter_flow():
    async for name_input in receive_input(GreeterInput, timeout=None, with_metadata=True):
        print(f"Hello, {name_input.value}!")
```

!!! warning "The type used in `receive_input` and `send_input` must match"
For a flow to receive input, the sender must use the same type that the receiver is receiving. This means that if the receiver is receiving `GreeterInput`, the sender must send `GreeterInput`. If the receiver is receiving `GreeterInput` and the sender sends `str` input that Prefect automatically upgrades to a `RunInput` class, the types won't match, so the receiving flow run won't receive the input.

### Keeping track of inputs you've already seen

By default, each time you call `receive_input`, you get an iterator that iterates over all known inputs, starting with the first received. There are common situations in which you'll want to keep track of inputs you've already seen and avoid seeing them again when you call `receive_input`, such as:

1. The flow receiving input is designed to suspend and resume later
2. The flow receiving input calls `receive_input` in a loop (we'll see an example of this later in this guide)

The first case requires saving the list of seen inputs somewhere that a future flow run can see them, e.g. a `JSONBlock` scoped to a workspace or other external storage. The second case is easier: you can use a `set` within your flow:

```python
from prefect import flow
from prefect.input.run_input import receive_input


@flow
async def greeter():
    # In this case, there is no reason to save inputs, so this just shows
    # how it works. Later in this guide, you will see an example where we
    # really do need to save the seen inputs!
    seen_names = set()

    async for name_input in receive_input(
        str, with_metadata=True, poll_interval=0.1, timeout=None, exclude_keys=seen_names
    ):
        await name_input.respond(f"Hello, {name_input.value}!")
        seen_names.add(name_input.metadata.key)
```

!!! note "Run inputs have keys, not IDs"
    Prefect stores run inputs in key-value storage, so the easiest way to keep track of inputs your flow run has seen is by saving the *key* of each run input. The key for a run input is stored in the `metadata.key` field on a `RunInput` instance.

#### Keeping track of seen input keys

That means we need to keep track of inputs we've seen, which we do by adding the *key* of the flow run input to the `seen_greetings` set.

### Responding to the input's sender

When your flow receives input from another flow, Prefect knows who the _sender_ was, so the receiving flow can respond by calling the `respond` method on the `RunInput` instance the flow received. There are a couple of requirements:

1. You will need to pass in a `BaseModel` or `RunInput`, or use `with_metadata=True`
2. The sending flow must be receiving the same type.

The `respond` method is equivalent to calling `send_input(..., flow_run_id=sending_flow_run.id)`, but your flow doesn't need to know the sending flow run's ID.

Now that we know about `respond`, let's make our `greeter_flow` respond to name inputs instead of printing them:

```python
from prefect import flow
from prefect.input.run_input import receive_input


@flow
async def greeter():
    async for name_input in receive_input(str, with_metadata=True, timeout=None):
        await name_input.respond(f"Hello, {name_input.value}!")
```

Cool! There's one problem left: this flow runs forever! We need a way to signal that it should exit. Let's keep things simple and teach it to look for a special string:

```python
from prefect import flow
from prefect.input.run_input import receive_input



EXIT_SIGNAL = "__EXIT__"


@flow
async def greeter():
    async for name_input in receive_input(
        str, with_metadata=True, poll_interval=0.1, timeout=None
    ):
        if name_input.value == EXIT_SIGNAL:
            print("Goodbye!")
            return
        await name_input.respond(f"Hello, {name_input.value}!")
```

With a `greeter` flow in place, now we're ready to create the flow that sends `greeter` names!

### Sending input

You can send input to a flow with the `send_input` function. This works similarly to `receive_input`, taking the same types for the `run_input` argument (basic types like `str`, `BaseModel` subclasses, and `RunInput` subclasses).

!!! note "When can you send input to a flow run?"
    You can send input to a flow run as soon as you have the flow run's ID. The flow does not have to be receiving input for you to send input. If you send a flow input before it is receiving, it will see your input when it calls `receive_input` (as long as the types in the `send_input` and `receive_input` calls match!)

Next, we'll create a `sender` flow that starts a `greeter` flow run and then enters a loop, continuously getting input from the terminal and sending it to the greeter flow:

```python
@flow
async def sender():
    greeter_flow_run = await run_deployment(
        "greeter/send-receive", timeout=0, as_subflow=False
    )

    greetings_seen = set()

    while True:
        name = input("What is your name? ")
        if not name:
            continue


        if name == "q" or name == "quit":
            await send_input(EXIT_SIGNAL, flow_run_id=greeter_flow_run.id)
            print("Goodbye!")
            break

        await send_input(name, flow_run_id=greeter_flow_run.id)

        async for greeting in receive_input(
            str, with_metadata=True, exclude_keys=greetings_seen, timeout=None, poll_interval=0.1
        ):
            print(greeting)
            greetings_seen.add(greeting.metadata.key)
            break
```

There's more going on here than in `greeter`, so let's take a closer look at the pieces.

First, we use `run_deployment` to start a `greeter` flow run. This means we must have a worker or `flow.serve()` running in separate process. That process will begin running `greeter` while `sender` continues to execute. Calling `run_deployment(..., timeout=0)` ensures that `sender` won't wait for the `greeter` flow run to complete, because it's running a loop and will only exit when we send `EXIT_SIGNAL`.

Next, what's going on with `greetings_seen`? This flow works by entering a loop, and on each iteration of the loop, the flow asks for terminal input, sends that to the `greeter` flow, and then runs *another loop* when it calls `async for greeting in receive_input(...)`. As we saw earlier in this guide, `receive_input` always starts at the beginning of all input this flow run received. Keeping track of the inputs we've already seen in the `greetings_seen` set allows us to pass this set in for the `exclude_keys` parameter each time we reenter the loop and call `receive_input` again.

Next, we let the terminal user who ran this flow exit by entering the string `q` or `quit`. When that happens, we send the `greeter` flow an exit signal so it will shut down too.

Net, we send the new name to `greeter`. We know that `greeter` is going to send back a greeting as a string, so we immediately begin waiting for new string input. When we receive the greeting, we print it, note the key as one we've seen, and break out of the `async for greeting in receive_inpu(...)` loop to continue the loop that gets terminal input.
