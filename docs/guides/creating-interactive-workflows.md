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

Flows can now pause or suspend execution and automatically resume when they receive type-checked input in Prefect's UI. Flows can also send and receive type-checked input at any time while running, without pausing or suspending. This guide will show you how to use these features to build _interactive workflows_.

!!! note "A note on async Python syntax"
    Most of the example code in this section uses async Python functions and `await`. However, as with other Prefect features, you can call these functions with or without `await`.

## Pausing or suspending a flow until it receives input

You can pause or suspend a flow until it receives input from a user in Prefect's UI. This is useful when you need to ask for additional information or feedback before resuming a flow. Such workflows are often called [human-in-the-loop](https://hai.stanford.edu/news/humans-loop-design-interactive-ai-systems) (HITL) systems.

!!! note "What is human-in-the-loop interactivity used for?"

    Approval workflows that pause to ask a human to confirm whether a workflow should continue are very common in the business world. Certain types of [machine learning training](https://link.springer.com/article/10.1007/s10462-022-10246-w) and artificial intelligence workflows benefit from incorporating HITL design.

### Waiting for input

To receive input while paused or suspended use the `wait_for_input` parameter in the `pause_flow_run` or `suspend_flow_run` functions. This parameter accepts one of the following:

- A built-in type like `int` or `str`, or a built-in collection like `List[int]`
- A `pydantic.BaseModel` subclass
- A subclass of `prefect.input.RunInput`

!!! tip "When to use a `RunModel` or `BaseModel` instead of a built-in type"
    There are a few reasons to use a `RunModel` or `BaseModel`. The first is that when you let Prefect automatically create one of these classes for your input type, the field that users will see in Prefect's UI when they click "Resume" on a flow run is named `value` and has no help text to suggest what the field is. If you create a `RunInput` or `BaseModel`, you can change details like the field name, help text, and default value, and users will see those reflected in the in the "Resume" form.

The simplest way to pause or suspend and wait for input is to pass a type:

```python
from prefect import flow, pause_flow_run

@flow
def greet_user():
    logger = get_run_logger()

    user_input = pause_flow_run(wait_for_input=str)

    logger.info(f"Hello, {user_input.name}!")
```

In this example, the flow run will pause until a user clicks the Resume button in the Prefect UI, enters a name, and submits the form.

!!! note "What types can you pass for `wait_for_input`?"

    When you pass a built-in type such as `int` as an argument for the `wait_for_input` parameter to `pause_flow_run` or `suspend_flow_run`, Prefect automatically creates a Pydantic model containing one field annotated with the type you specified. This means you can use [any type annotation that Pydantic accepts for model fields](https://docs.pydantic.dev/1.10/usage/types/) with these functions.

Instead of a built-in type, you can pass in a `pydantic.BaseModel` class. This is useful if you already have `BaseModels` you want to use:

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

The most important parameter to the `send_input` and `receive_input` functions is `run_type`, which should be one of the following:

- A type such as `int` or `str`
- A `pydantic.BaseModel` subclass
- A subclass of `prefect.input.RunInput`

!!! type "When to use a `BaseModel` or `RunInput` instead of a built-in type"
    When you send and receive input with `send_input` and `receive_input` does not involve generating forms in the UI, so how an input type like `List[in]` might appear in the UI is not an issue. However, when you find yourself using nested collection types, such as lists of tuples, e.g. `List[Tuple[str, float]])`, consider placing the field in an explicit `BaseModel` or `RunInput`. This is so that validation will happen  validating the data sent  Prefect may not be able to prevent your flow from receiving collections of the wrong type, especially if you are receiving nested collection types, such as lists of tuples, e.g. (`List[Tuple[str, float]])`. In a case like lists of tuples,  we know exactly what you want to receive, but we can't always tell if an input 



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

When you pass a type such as `str` into `receive_input`, Prefect creates a `RunInput` class to manage your input automatically. When your flow receives input of this type, Prefect uses this `RunInput` class to validate the input. If the validation succeeds, your flow sees the input in the type you specified. In this example, if the flow received a valid string as input, the variable `name_input` would contain the string value.

If, instead, you specify a `BaseModel`, Prefect upgrades your `BaseModel` to a `RunInput` class, and the variable your flow sees &mdash in this case, `name_input` &mdash is a `RunInput` instance. Of course, if you pass in a `RunInput` class, no upgrade is needed, and you'll get a `RunInput` instance.

If you prefer to keep things simple and pass types such as `str` into `receive_input`, you need access to the generated `RunInput` instance. Pass `with_metadata=True` to `receive_input`:

```python
from prefect import flow
from prefect.input.run_input import receive_input


@flow
async def greeter_flow():
    async for name_input in receive_input(str, timeout=None, with_metadata=True):
        print(f"Hello, {name_input.value}!")

```

Notice that we are now printing `name_input.value`. When Prefect generates a `RunInput` for you from a built-in type, the `RunInput` class has a single field, `value`, that uses a type annotation matching the type you specified. So if you call `receive_input` like this: `receive_input(str, with_metadata=True)`, that's equivalent to manually creating the following `RunInput` class and `receive_input` call:

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

By default, each time you call `receive_input`, you get an iterator that iterates over all known inputs, starting with the first received. The iterator will keep track of your current position as you iterate over it, or you can call `next()` to explicitly get the next input. If you're using the iterator in a loop, you should probably assign it to a variable:

```python
from prefect import flow, get_client
from prefect.deployments.deployments import run_deployment
from prefect.input.run_input import receive_input, send_input

EXIT_SIGNAL = "__EXIT__"


@flow
async def sender():
    greeter_flow_run = await run_deployment(
        "greeter/send-receive", timeout=0, as_subflow=False
    )
    client = get_client()
    
    # Assigning the `receive_input` iterator to a variable outside of the the
    # `while True` loop allows us to continue iterating over inputs in
    # subsequent passes through the while loop without losing our position.
    receiver = receive_input(str, with_metadata=True, timeout=None, poll_interval=0.1)

    while True:
        name = input("What is your name? ")
        if not name:
            continue

        if name == "q" or name == "quit":
            await send_input(EXIT_SIGNAL, flow_run_id=greeter_flow_run.id)
            print("Goodbye!")
            break

        await send_input(name, flow_run_id=greeter_flow_run.id)

        # Saving the iterator outside of the while loop and calling next() on
        # each iteration of the loop ensures that we're always getting the
        # newest greeting. If we had instead called `receive_input` here, we
        # would always get the _first_ greeting this flow received, print it,
        # and then ask for a new name.
        greeting = await receiver.next()
        print(greeting)
``

So, an iterator helps to keep track of the inputs your flow has already received. But what if you want your flow to suspend and then resume later, picking up where it left off? In that case, you will need to save the keys of the inputs you've seen so that the flow can read them back out when it resumes. You might use a [Block](/concepts/blocks/), such as a `JSONBlock`, scoped to a workspace.

The following flow receives input for 30 seconds then suspends itself, which exits the flow and tears down infrastructure:

```python
from prefect import flow, get_run_logger, suspend_flow_run
from prefect.blocks.system import JSON
from prefect.context import get_run_context
from prefect.input.run_input import receive_input


EXIT_SIGNAL = "__EXIT__"


@flow
async def greeter():
    logger = get_run_logger()
    run_context = get_run_context()
    assert run_context.flow_run, "Could not see my flow run ID"

    block_name = f"{run_context.flow_run.id}-seen-ids"

    try:
        seen_keys_block = await JSON.load(block_name)
    except ValueError:
        seen_keys_block = JSON(
            value=[],
        )

    try:
        async for name_input in receive_input(
            str, with_metadata=True, poll_interval=0.1, timeout=30, exclude_keys=seen_keys_block.value
        ):
            if name_input.value == EXIT_SIGNAL:
                print("Goodbye!")
                return
            await name_input.respond(f"Hello, {name_input.value}!")

            seen_keys_block.value.append(name_input.metadata.key)
            await seen_keys_block.save(name=block_name, overwrite=True)
    except TimeoutError:
        logger.info("Suspending greeter after 30 seconds of idle time")
        await suspend_flow_run(timeout=10000)
```

As this flow processes name input, it adds the *key* of the flow run input to the `seen_keys_block`. When the flow later suspends and then resumes, it reads the keys it has already seen out of the JSON Block and passes them as the `exlude_keys` parameter to `receive_input`.

### Responding to the input's sender

When your flow receives input from another flow, Prefect knows the sending flow run ID, so the receiving flow can respond by calling the `respond` method on the `RunInput` instance the flow received. There are a couple of requirements:

1. You will need to pass in a `BaseModel` or `RunInput`, or use `with_metadata=True`
2. The flow you are responding to must receive the same type of input you send in order to see it.

The `respond` method is equivalent to calling `send_input(..., flow_run_id=sending_flow_run.id)`, but with `respond`, your flow doesn't need to know the sending flow run's ID.

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

You can send input to a flow with the `send_input` function. This works similarly to `receive_input` and, like that function, accepts the same `run_input` argument, which can be a built-in type such as `str`, or else a `BaseModel` or `RunInput` subclass.

!!! note "When can you send input to a flow run?"
    You can send input to a flow run as soon as you have the flow run's ID. The flow does not have to be receiving input for you to send input. If you send a flow input before it is receiving, it will see your input when it calls `receive_input` (as long as the types in the `send_input` and `receive_input` calls match!)

Next, we'll create a `sender` flow that starts a `greeter` flow run and then enters a loop, continuously getting input from the terminal and sending it to the greeter flow:

```python
@flow
async def sender():
    greeter_flow_run = await run_deployment(
        "greeter/send-receive", timeout=0, as_subflow=False
    )
    receiver = receive_input(str, timeout=None, poll_interval=0.1)
    client = get_client()

    while True:
        flow_run = await client.read_flow_run(greeter_flow_run.id)
        
        if not flow_run.state or not flow_run.state.is_running():
            continue
 
        name = input("What is your name? ")
        if not name:
            continue

        if name == "q" or name == "quit":
            await send_input(EXIT_SIGNAL, flow_run_id=greeter_flow_run.id)
            print("Goodbye!")
            break

        await send_input(name, flow_run_id=greeter_flow_run.id)
        greeting = await receiver.next()
        print(greeting)
```

There's more going on here than in `greeter`, so let's take a closer look at the pieces.

First, we use `run_deployment` to start a `greeter` flow run. This means we must have a worker or `flow.serve()` running in separate process. That process will begin running `greeter` while `sender` continues to execute. Calling `run_deployment(..., timeout=0)` ensures that `sender` won't wait for the `greeter` flow run to complete, because it's running a loop and will only exit when we send `EXIT_SIGNAL`.

Next, we capture the iterator returned by `receive_input` as `receiver`. This flow works by entering a loop, and on each iteration of the loop, the flow asks for terminal input, sends that to the `greeter` flow, and then runs `receiver.next()` to wait until it receives the response from `greeter`.

Next, we let the terminal user who ran this flow exit by entering the string `q` or `quit`. When that happens, we send the `greeter` flow an exit signal so it will shut down too.

Finally, we send the new name to `greeter`. We know that `greeter` is going to send back a greeting as a string, so we immediately wait for new string input. When we receive the greeting, we print it and continue the loop that gets terminal input.

### Seeing a complete example

Finally, let's see a complete example of using `send_input` and `receive_input`. Here is what the `greeter` and `sender` flows look like together:

```python
import asyncio
import sys
from prefect import flow, get_client
from prefect.blocks.system import JSON
from prefect.context import get_run_context
from prefect.deployments.deployments import run_deployment
from prefect.input.run_input import receive_input, send_input


EXIT_SIGNAL = "__EXIT__"


@flow
async def greeter():
    run_context = get_run_context()
    assert run_context.flow_run, "Could not see my flow run ID"

    block_name = f"{run_context.flow_run.id}-seen-ids"

    try:
        seen_keys_block = await JSON.load(block_name)
    except ValueError:
        seen_keys_block = JSON(
            value=[],
        )

    async for name_input in receive_input(
        str, with_metadata=True, poll_interval=0.1, timeout=None
    ):
        if name_input.value == EXIT_SIGNAL:
            print("Goodbye!")
            return
        await name_input.respond(f"Hello, {name_input.value}!")

        seen_keys_block.value.append(name_input.metadata.key)
        await seen_keys_block.save(name=block_name, overwrite=True)


@flow
async def sender():
    greeter_flow_run = await run_deployment(
        "greeter/send-receive", timeout=0, as_subflow=False
    )
    receiver = receive_input(str, timeout=None, poll_interval=0.1)
    client = get_client()

    while True:
        flow_run = await client.read_flow_run(greeter_flow_run.id)

        if not flow_run.state or not flow_run.state.is_running():
            continue

        name = input("What is your name? ")
        if not name:
            continue

        if name == "q" or name == "quit":
            await send_input(EXIT_SIGNAL, flow_run_id=greeter_flow_run.id)
            print("Goodbye!")
            break

        await send_input(name, flow_run_id=greeter_flow_run.id)
        greeting = await receiver.next()
        print(greeting)


if __name__ == "__main__":
    if sys.argv[1] == "greeter":
        asyncio.run(greeter.serve(name="send-receive"))
    elif sys.argv[1] == "sender":
        asyncio.run(sender())
``` 

To run the example, you'll need a Python environment with Prefect installed, pointed at either open-source Prefect or Prefect Cloud.

With your environment set up, start a flow runner in one terminal with the following command:
    $ python <filename> greeter
    
For example, with Prefect Cloud, you should see output like this:
```
╭──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Your flow 'greeter' is being served and polling for scheduled runs!                              │
│                                                                                                  │
│ To trigger a run for this flow, use the following command:                                       │
│                                                                                                  │
│         $ prefect deployment run 'greeter/send-receive'                                          │
│                                                                                                  │
│ You can also run your flow via the Prefect UI:                                                   │
│ https://app.prefect.cloud/account/...(a URL for your account)                                    │
│                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

Then start the greeter in another process in another terminal:
    $ python <filename> sender

You should see:
```
11:38:41.800 | INFO    | prefect.engine - Created flow run 'gregarious-owl' for flow 'sender'
11:38:41.802 | INFO    | Flow run 'gregarious-owl' - View at https://app.prefect.cloud/account/...
What is your name?
```

Type a name and press the enter key to see a greeting, and you'll see sending and receiving in action:

```
What is your name? andrew
Hello, andrew!
```
