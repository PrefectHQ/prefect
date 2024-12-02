<p align="center"><img src="https://github.com/PrefectHQ/prefect/assets/3407835/c654cbc6-63e8-4ada-a92a-efd2f8f24b85" width=1000></p>

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-client/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-client?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/prefecthq/prefect/" alt="Stars">
        <img src="https://img.shields.io/github/stars/prefecthq/prefect?color=0052FF&labelColor=090422" /></a>
    <a href="https://pepy.tech/badge/prefect-client/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-client?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/prefecthq/prefect/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/prefecthq/prefect?color=0052FF&labelColor=090422" /></a>
    <br>
    <a href="https://prefect.io/slack" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://www.youtube.com/c/PrefectIO/" alt="YouTube">
        <img src="https://img.shields.io/badge/youtube-watch_videos-red.svg?color=0052FF&labelColor=090422&logo=youtube" /></a>
</p>

# prefect-client

The `prefect-client` package is a minimal-installation of `prefect` which is designed for interacting with Prefect Cloud
or remote any `prefect` server. It sheds some functionality and dependencies in exchange for a smaller installation size,
making it ideal for use in lightweight or ephemeral environments. These characteristics make it ideal for use in lambdas
or other resource-constrained environments.


## Getting started

`prefect-client` shares the same installation requirements as prefect. To install, make sure you are on Python 3.9 or
later and run the following command:

```bash
pip install prefect-client
```

Next, ensure that your `prefect-client` has access to a remote `prefect` server by exporting the `PREFECT_API_KEY`
(if using Prefect Cloud) and `PREFECT_API_URL` environment variables. Once those are set, use the package in your code as
you would normally use `prefect`!


For example, to remotely trigger a run a deployment:

```python
from prefect.deployments import run_deployment


def my_lambda(event):
    ...
    run_deployment(
        name="my-flow/my-deployment",
        parameters={"foo": "bar"},
        timeout=0,
    )

my_lambda({})
```

To emit events in an event driven system:

```python
from prefect.events import emit_event


def something_happened():
    emit_event("my-event", resource={"prefect.resource.id": "foo.bar"})

something_happened()
```


Or just interact with a `prefect` API:
```python
from prefect.client.orchestration import get_client


async def query_api():
    async with get_client() as client:
        limits = await client.read_concurrency_limits(limit=10, offset=0)
        print(limits)


query_api()
```


## Known limitations
By design, `prefect-client` omits all CLI and server components. This means that the CLI is not available for use
and attempts to access server objects will fail. Furthermore, some classes, methods, and objects may be available
for import in `prefect-client` but may not be "runnable" if they tap into server-oriented functionality. If you
encounter such a limitation, feel free to [open an issue](https://github.com/PrefectHQ/prefect/issues/new/choose)
describing the functionality you are interested in using and we will do our best to make it available.


## Next steps

There's lots more you can do to orchestrate and observe your workflows with Prefect!
Start with our [friendly tutorial](https://docs.prefect.io/tutorials) or explore the [core concepts of Prefect workflows](https://docs.prefect.io/concepts/).

## Join the community

Prefect is made possible by the fastest growing community of thousands of friendly data engineers. Join us in building a new kind of workflow system. 
The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more about Prefect, ask questions, or get help with workflow design. 
All community forums, including code contributions, issue discussions, and Slack messages are subject to our [Code of Conduct](https://github.com/PrefectHQ/prefect/blob/main/CODE_OF_CONDUCT.md).

## Contribute

See our [documentation on contributing to Prefect](https://docs.prefect.io/contributing/overview/).

Thanks for being part of the mission to build a new kind of workflow system and, of course, **happy engineering!**
