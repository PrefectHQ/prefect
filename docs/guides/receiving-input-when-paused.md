---
description: Learn how to receive input when a flow run is paused or suspended.
tags:
    - flow run
    - pause
    - suspend
    - input
search:
  boost: 2
---

# Receiving input when pausing or suspending a flow run
!!! tip "Experimental"

    The `wait_for_input` parameter used in the `pause_flow_run` or `suspend_flow_run` methods is an experimental feature. The interface or behavior of this feature may change without warning in future releases. 

    If you encounter any issues, please let us know in Slack or with a Github issue.


When a flow run is paused or suspended, you can receive input from the user. This is useful when you need to ask the user for additional information or feedback before resuming the flow run.

## Waiting for input

To receive input you must use the `wait_for_input` parameter in the `pause_flow_run` or `suspend_flow_run` methods. This parameter accepts a subclass of `prefect.input.RunInput`. `RunInput` is a subclass of `pydantic.BaseModel` and can be used to define the input that you want to receive:

```python
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

You can set default values for fields in your model by using the `with_initial_data` method. This is particularly useful when you want to provide default values for fields such as `title` and `description` that are part of the base `RunInput` class and are displayed in the UI when resuming a flow run.

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

Prefect uses the fields and type hints on your `RunInput` subclass to validate the general structure of input your flow run receives, but you might require more complex validation. If you do, you can use Pydantic's validation methods.

```python
import pydantic
from prefect.input import RunInput

class UserAgeInput(RunInput):
    age: int

    @pydantic.validator("age")
    def validate_age(cls, value):
        min_age = 18
        max_age = 99

        if not min_age <= value <= max_age:
            raise ValueError(f"Age must be between {min_age} and {max_age}")
        
        return value
```

In this case, we are using Pydantic's `validator` decorator to define a custom validation method for the `age` field. We can use it in a flow like this:

```python
import pydantic
from prefect import flow, pause_flow_run

class UserAgeInput(pydantic.BaseModel):
    age: int

    @pydantic.validator("age")
    def validate_age(cls, value):
        min_age = 18
        max_age = 99

        if not min_age <= value <= max_age:
            raise ValueError(f"Age must be between {min_age} and {max_age}")

        return value

@flow
def get_user_age():
    user_age_input = pause_flow_run(wait_for_input=UserAgeInput)
```

If a user enters an invalid age of `hello`, the flow run will not resume and the user will receive a validation error. However, if the user enters a number that is a valid integer but that is not between 18 and 99, the flow run will resume, and `pause_flow_run` will raise a `ValidationError` exception.

One way to handle this and ensure that the user enters valid input is to use a `while` loop and pause again if the `ValidationError` exception is raised:

```python
import pydantic
from prefect import flow, pause_flow_run

class UserAgeInput(pydantic.BaseModel):
    age: int

    @pydantic.validator("age")
    def validate_age(cls, value):
        min_age = 18
        max_age = 99

        if not min_age <= value <= max_age:
            raise ValueError(f"Age must be between {min_age} and {max_age}")

        return value

@flow
def get_user_age():
    logger = get_run_logger()

    user_age = None

    while user_age is None:
        try:
            user_age_data = pause_flow_run(wait_for_input=UserAgeInput)
        except pydantic.ValidationError as exc:
            logger.error(f"Invalid age: {exc}")
        else:
            user_age = user_age_data.age
```

This will cause the flow run to continually pause until the user enters a valid age.
