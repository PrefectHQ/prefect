# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any

import prefect


class Constant(prefect.Task):
    def __init__(self, value: Any, name: str = None, **kwargs: Any):

        self.value = value

        # set the name from the value
        if name is None:
            name = repr(self.value)
            if len(name) > 8:
                name = "Constant[{}]".format(type(self.value).__name__)

        super().__init__(name=name, **kwargs)

    def run(self):  # type: ignore
        return self.value
