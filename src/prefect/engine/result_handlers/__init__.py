"""
:::warning
Result handlers have been deprecated in 0.11.0. For Prefect installations 0.11.0+, at runtime, all result handlers configured on a flow will be autoconverted into a matching subclass of `Result` from `prefect.engine.results`.
:::

Result handler is a specific implementation of a `read` / `write` interface for handling data.
The only requirement for a Result handler implementation is that the `write` method returns a JSON-compatible object.

As a toy example, suppose we want to implement a result handler which stores data on some webserver that we have access to.
Our custom result handler might look like:

```python
import json
import requests
from prefect.engine.result_handlers import ResultHandler


class WebServerHandler(ResultHandler):
    def write(self, obj):
        '''
        Stores a JSON-compatible object on our webserver and returns
        the URL for retrieving it later
        '''
        r = requests.post("http://foo.example.bar/", data={"payload": json.dumps(obj)})
        url = r.json()['url']
        return url

    def read(self, url):
        '''
        Given a URL on our webserver, retrieves the object and deserializes it.
        '''
        r = requests.get(url)
        json_obj = r.json()['payload']
        return json.loads(json_obj)
```

Note that we could also optionally override the `__init__` method of our class if we wanted to allow for additional configuration.
"""

from prefect.engine.result_handlers.result_handler import ResultHandler
from prefect.engine.result_handlers.constant_result_handler import ConstantResultHandler
from prefect.engine.result_handlers.json_result_handler import JSONResultHandler
from prefect.engine.result_handlers.local_result_handler import LocalResultHandler
from prefect.engine.result_handlers.secret_result_handler import SecretResultHandler

try:
    from prefect.engine.result_handlers.gcs_result_handler import GCSResultHandler
except ImportError:
    pass

try:
    from prefect.engine.result_handlers.s3_result_handler import S3ResultHandler
except ImportError:
    pass

try:
    from prefect.engine.result_handlers.azure_result_handler import AzureResultHandler
except ImportError:
    pass
