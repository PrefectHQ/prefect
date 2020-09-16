# Contributing

Contributing to Prefect's task library is a great way to assist in open source development! Generally
users have contributed tasks to the task library that accomplish a specific goal or action. If there is a
library, tool, or framework that you commonly use or if you have a preferred abstraction to performing
some task we highly encourage contributions to the library. Additionally if you are a developer who has
built something then providing a simple way for Prefect users to interact with it has the potential to
increase adoption.

Not to mention that we occasionally also send Prefect swag to some of our open source contributors!

<script>
import { Tweet } from 'vue-tweet-embed/dist'

export default {
    components: {Tweet}
}
</script>

<Tweet id="1298298873878847490"></Tweet>

## Task Structure

This snippet below is the general structure of a task contained in the task library. All you need to do
is define the task's `__init__` and `run` functions! The `run` function is where any of your task's logic
will live.

```python
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

class YourTask(Task):
    """
    Task for doing something

    Args:
        - your_kwarg (string, optional): an optional kwarg
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        your_kwarg: str = None,
        **kwargs: Any
    ):
        self.your_kwarg = your_kwarg
        super().__init__(**kwargs)

    # Allows init kwargs to be passed to the run function if they are not overridden
    @defaults_from_attrs("your_kwarg")
    def run(self, your_kwarg: str = None) -> str:
        """
        Run your task

        Args:
            - your_kwarg (string, optional): an optional kwarg

        Returns:
            - string: description of what it returned
        """

        # Place your specific task run logic inside this function
        return use_your_library(your_kwarg)
```

For more examples of how the other tasks in the task library look check out the directory
containing all of the [task library code](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/tasks).

For more information on contributing to the Prefect library as whole check out the
[development documentation](/core/development/overview.html).

## Testing

Due to the nature of the tasks in the task library interacting with a wide range of services from various
contributors it is not condusive for Prefect integration tests to maintain tests that communicate with
all of these services. Because of this, it is integral that users who are contributing tasks to the task
library test their tasks themselves against whichever services the tasks interact with.

However, we do still encourage the contribution of unit tests! The unit tests for tasks in the task
library generally test that proper variables are set and used with accompanying mocks for the services
that they interact with. For examples of how some of the other tasks in the task library are tested check
out the [tasks testing directory](https://github.com/PrefectHQ/prefect/tree/master/tests/tasks).
