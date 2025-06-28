"""
Asynchronous client implementation for communicating with the [Prefect REST API](/api-ref/rest-api/).

Explore the client by communicating with an in-memory webserver - no setup required:

<div class="termy">
```
$ # start python REPL with native await functionality
$ python -m asyncio
from prefect.client.orchestration import get_client
async with get_client() as client:
    response = await client.hello()
    print(response.json())
👋
```
</div>
"""

from collections.abc import Callable
from typing import Any
from prefect._internal.compatibility.migration import getattr_migration

__getattr__: Callable[[str], Any] = getattr_migration(__name__)
