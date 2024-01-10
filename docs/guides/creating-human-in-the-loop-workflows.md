---
description: Learn how to create human-in-the-loop workflows with Prefect.
tags:
    - flow run
    - pause
    - suspend
    - input
search:
  boost: 2
---

# Creating Human-in-the-Loop Workflows
!!! warning "Experimental"

    The `wait_for_input` parameter used in the `pause_flow_run` or `suspend_flow_run` functions is an experimental feature. The interface or behavior of this feature may change without warning in future releases. 

    If you encounter any issues, please let us know in [Slack](https://www.prefect.io/slack/) or with a [Github](https://github.com/PrefectHQ/prefect) issue.


When a flow run is paused or suspended, you can receive input from the user. This is useful when you need to ask the user for additional information or feedback before resuming the flow run.

## Waiting for input

To receive input you must use the `wait_for_input` parameter in the `pause_flow_run` or `suspend_flow_run` functions. This parameter accepts a subclass of `prefect.input.RunInput`. `RunInput` is a subclass of `pydantic.BaseModel` and can be used to define the input that you want to receive:

```python
from prefect.input import RunInput

class UserNameInput(RunInput):
    name: str
```

In this case we are defining a `UserNameInput` class that will receive a `name` string from the user. You can then use this class in the `wait_for_input` parameter:

```python
@flow
async def greet_user():
    logger = get_run_logger()

    user_input = await pause_flow_run(
        wait_for_input=UserNameInput
    )

    logger.info(f"Hello, {user_input.name}!")
```

When the flow run is paused, the user will be prompted to enter a name. If the user does not enter a name, the flow run will not resume. If the user enters a name, the flow run will resume and the `user_input` variable will contain the name that the user entered.

## Providing initial data

You can set default values for fields in your model by using the `with_initial_data` method. This is useful when you want to provide default values for the fields in your own `RunInput` subclasses.

Expanding on the example above, you could default the `name` field to something anonymous.

```python
@flow
async def greet_user():
    logger = get_run_logger()

    user_input = await pause_flow_run(
        wait_for_input=UserNameInput.with_initial_data(name="anonymous")
    )

    if user_input.name == "anonymous":
        logger.info("Hello, stranger!")
    else:
        logger.info(f"Hello, {user_input.name}!")
```

## Handling custom validation

Prefect uses the fields and type hints on your `RunInput` subclass to validate the general structure of input your flow run receives, but you might require more complex validation. If you do, you can use Pydantic [validators](https://docs.pydantic.dev/1.10/usage/validators/).

!!! warning "Custom validation runs after the flow run resumes"
    Prefect transforms the type annotations in your `RunInput` class to a JSON schema and use that schema in the UI to do client-side validation. However, custom validation requires running logic defined in your `RunInput` class. This happens *after the flow resumes*, so you'll probably want to handle it explicitly in your flow. Continue reading for an example best practice.

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
from prefect import flow
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
from prefect import flow, pause_flow_run, get_run_logger
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
