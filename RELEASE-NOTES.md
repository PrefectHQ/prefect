# Prefect Release Notes

## Release 2.15.0

### 🔧 Task runs now execute on the main thread

We are excited to announce that task runs are now executed on the main thread! 

When feasible, task runs are now executed on the main thread instead of a worker thread. Previously, all task runs were run in a new worker thread. This allows objects to be passed to and from tasks without worrying about thread safety unless you have opted into concurrency. For example, an HTTP client or database connection can be shared between a flow and its tasks now (unless synchronous concurrency is used). Some asynchronous and sequential use cases may see performance improvements.

Consider the following example:

```python
import sqlite3
from prefect import flow, task

db = sqlite3.connect("threads.db")

try:
    db.execute("CREATE TABLE fellowship(name)")
except sqlite3.OperationalError:
    pass
else:
    db.commit()

db.execute("DELETE FROM fellowship")
db.commit()

cur = db.cursor()


@task
def my_task(name: str):
    global db, cur

    cur.execute('INSERT INTO fellowship VALUES (?)', (name,))

    db.commit()


@flow
def my_flow():
    global db, cur

    for name in ["Frodo", "Gandalf", "Gimli", "Aragorn", "Legolas", "Boromir", "Samwise", "Pippin", "Merry"]:
        my_task(name)

    print(cur.execute("SELECT * FROM fellowship").fetchall())

    db.close()


if __name__ == "__main__":
    my_flow()
```

In previous versions of Prefect, running this example would result in an error like this:

```python
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 7977619456 and this is thread id 6243151872.
```

But now, with task runs executing on the main thread, this example will run without error! We're excited this change makes Prefect even more intuitive and flexible!

See the following pull request for implementation details:
    - https://github.com/PrefectHQ/prefect/pull/11930

### 🔭 Monitor deployment runs triggered via the CLI

You can monitor the status of a flow run created from a deployment via the CLI. This is useful for observing a flow run's progress without navigating to the UI.

To monitor a flow run started from a deployment, use the `--watch` option with `prefect deployment run`:

```console
prefect deployment run --watch <slugified-flow-name>/<slugified-deployment-name>
```

See the following pull request for implementation details:
    - https://github.com/PrefectHQ/prefect/pull/11702

### Enhancements

- Enable work queue status in the UI by default — https://github.com/PrefectHQ/prefect/pull/11976 & https://github.com/PrefectHQ/prefect-ui-library/pull/2080

### Fixes
- Update vendored `starlette` version to resolve vulnerability in `python-mulipart` — https://github.com/PrefectHQ/prefect/pull/11956
- Fix display of interval schedules created with a different timezone than the current device - https://github.com/PrefectHQ/prefect-ui-library/pull/2090

### Experimental

- Prevent `RUNNING` -> `RUNNING` state transitions for autonomous task runs — https://github.com/PrefectHQ/prefect/pull/11975
- Provide current thread to the engine when submitting autonomous tasks — https://github.com/PrefectHQ/prefect/pull/11978
- Add intermediate `PENDING` state for autonomous task execution — https://github.com/PrefectHQ/prefect/pull/11985
- Raise exception when stopping task server — https://github.com/PrefectHQ/prefect/pull/11928

### Documentation
- Update work pools concepts page to include Modal push work pool — https://github.com/PrefectHQ/prefect/pull/11954
- Add details to `run_deployment` tags parameter documentation — https://github.com/PrefectHQ/prefect/pull/11955
- Add Helm chart link in Prefect server instance docs — https://github.com/PrefectHQ/prefect/pull/11970
- Clarify that async nested flows can be run concurrently — https://github.com/PrefectHQ/prefect/pull/11982
- Update work queue and flow concurrency information to include push work pools — https://github.com/PrefectHQ/prefect/pull/11974

### Contributors
- @zanieb

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.21...2.15.0

## Release 2.14.21

### Introducing work queue status

We're excited to unveil the new status indicators for work queues in Prefect's UI, enhancing your ability to oversee and control flow run execution within our hybrid work pools.

Work queues will now display one of three distinct statuses:

- `Ready` -  one or more online workers are actively polling the work queue
- `Not Ready` - no online workers are polling the work queue, signaling a need for intervention
- `Paused` - the work queue is intentionally paused, preventing execution

<p align="center">
<img width="1109" alt="Prefect dashboard snapshot" src="https://github.com/PrefectHQ/prefect/assets/42048900/e5bb0a33-1ae2-44a7-a64e-ef0d308fce7a">
</p>
<img width="1109" alt="work pools page work queues table here with work queues of all statuses" src="https://github.com/PrefectHQ/prefect/assets/42048900/834f0f66-79e9-420b-9d11-d771a5b8cf02">

With the introduction of work queue status, you'll notice the absence of deprecated work queue health indicators in the UI.

See the documentation on [work queue status](https://docs.prefect.io/latest/concepts/work-pools/#work-queues) for more information.


For now, this is an experimental feature, and can be enabled by running:
```console
prefect config set PREFECT_EXPERIMENTAL_ENABLE_WORK_QUEUE_STATUS=True
```

See the following pull request for implementation details:
    - https://github.com/PrefectHQ/prefect/pull/11829

### Fixes
- Remove unnecessary `WARNING` level log indicating a task run completed successfully — https://github.com/PrefectHQ/prefect/pull/11810
- Fix a bug where block placeholders declared in pull steps of the `deployments` section of a `prefect.yaml` file were not resolved correctly — https://github.com/PrefectHQ/prefect/pull/11740
- Use `pool_pre_ping` to improve stability for long-lived PostgreSQL connections — https://github.com/PrefectHQ/prefect/pull/11911

### Documentation
- Clarify Docker tutorial code snippet to ensure commands are run from the correct directory — https://github.com/PrefectHQ/prefect/pull/11833
- Remove beta tag from incident documentation and screenshots — https://github.com/PrefectHQ/prefect/pull/11921
- Update Prefect Cloud account roles docs to reflect renaming of previous "Admin" role to "Owner" and creation of new "Admin" role that cannot bypass SSO — https://github.com/PrefectHQ/prefect/pull/11925

### Experimental
- Ensure task subscribers can only pick up task runs they are able to execute — https://github.com/PrefectHQ/prefect/pull/11805
- Allow a task server to reuse the same task runner to speed up execution — https://github.com/PrefectHQ/prefect/pull/11806
- Allow configuration of maximum backlog queue size and maximum retry queue size for autonomous task runs — https://github.com/PrefectHQ/prefect/pull/11825

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.20...2.14.21

## Release 2.14.20

### Fixes
- Fix runtime bug causing missing work queues in UI — https://github.com/PrefectHQ/prefect/pull/11807

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.19...2.14.20

## Release 2.14.19

## Dynamic descriptions for paused and suspended flow runs
You can now include dynamic, markdown-formatted descriptions when pausing or suspending a flow run for human input. This description will be shown in the Prefect UI alongside the form when a user is resuming the flow run, enabling developers to give context and instructions to users when they need to provide input.

```python
from datetime import datetime
from prefect import flow, pause_flow_run, get_run_logger
from prefect.input import RunInput

class UserInput(RunInput):
    name: str
    age: int

@flow
async def greet_user():
    logger = get_run_logger()
    current_date = datetime.now().strftime("%B %d, %Y")

    description_md = f"""
**Welcome to the User Greeting Flow!**
Today's Date: {current_date}

Please enter your details below:
- **Name**: What should we call you?
- **Age**: Just a number, nothing more.
"""

    user_input = await pause_flow_run(
        wait_for_input=UserInput.with_initial_data(
            description=description_md, name="anonymous"
        )
    )

    if user_input.name == "anonymous":
        logger.info("Hello, stranger!")
    else:
        logger.info(f"Hello, {user_input.name}!")
```

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11776
- https://github.com/PrefectHQ/prefect/pull/11799

### Enhancements
- Enhanced `RunInput` saving to include descriptions, improving clarity and documentation for flow inputs — https://github.com/PrefectHQ/prefect/pull/11776
- Improved type hinting for automatic run inputs, enhancing the developer experience and code readability — https://github.com/PrefectHQ/prefect/pull/11796
- Extended Azure filesystem support with the addition of `azure_storage_container` for more flexible storage options — https://github.com/PrefectHQ/prefect/pull/11784
- Added deployment details to work pool information, offering a more comprehensive view of work pool usage — https://github.com/PrefectHQ/prefect/pull/11766

### Fixes
- Updated terminal based deployment operations to make links within panels interactive, enhancing user navigation and experience — https://github.com/PrefectHQ/prefect/pull/11774

### Documentation
- Revised Key-Value (KV) integration documentation for improved clarity and updated authorship details — https://github.com/PrefectHQ/prefect/pull/11770
- Further refinements to interactive flows documentation, addressing feedback and clarifying usage — https://github.com/PrefectHQ/prefect/pull/11772
- Standardized terminal output in documentation for consistency and readability — https://github.com/PrefectHQ/prefect/pull/11775
- Corrected a broken link to agents in the work pool concepts documentation, improving resource accessibility — https://github.com/PrefectHQ/prefect/pull/11782
- Updated examples for accuracy and to reflect current best practices — https://github.com/PrefectHQ/prefect/pull/11786
- Added guidance on providing descriptions when pausing flow runs, enhancing operational documentation — https://github.com/PrefectHQ/prefect/pull/11799

### Experimental
- Implemented `TaskRunFilterFlowRunId` for both client and server, enhancing task run filtering capabilities — https://github.com/PrefectHQ/prefect/pull/11748
- Introduced a subscription API for autonomous task scheduling, paving the way for more dynamic and flexible task execution — https://github.com/PrefectHQ/prefect/pull/11779
- Conducted testing to ensure server-side scheduling of autonomous tasks, verifying system reliability and performance — https://github.com/PrefectHQ/prefect/pull/11793
- Implemented a global collections metadata cache clearance between tests, improving test reliability and accuracy — https://github.com/PrefectHQ/prefect/pull/11794
- Initiated task server testing, laying the groundwork for comprehensive server-side task management — https://github.com/PrefectHQ/prefect/pull/11797

## New Contributors
* @thomasfrederikhoeck made their first contribution in https://github.com/PrefectHQ/prefect/pull/11784

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.18...2.14.19

## Release 2.14.18

### Fixes
- Allow prefect settings to accept lists — https://github.com/PrefectHQ/prefect/pull/11722
- Revert deprecation of worker webserver setting — https://github.com/PrefectHQ/prefect/pull/11758

### Documentation
- Expand docs on interactive flows, detailing `send_input` and `receive_input` — https://github.com/PrefectHQ/prefect/pull/11724
- Clarify that interval schedules use an anchor not start date — https://github.com/PrefectHQ/prefect/pull/11767

## New Contributors
* @clefelhocz2 made their first contribution in https://github.com/PrefectHQ/prefect/pull/11722

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.17...2.14.18

## Release 2.14.17

### **Experimental**: Non-blocking submission of flow runs to the `Runner` web server
You can now submit runs of served flows without blocking the main thread, from inside or outside a flow run. If submitting flows from inside a parent flow, these submitted runs will be tracked as subflows of the parent flow run.

<img width="1159" alt="Prefect flow run graph screenshot" src="https://github.com/PrefectHQ/prefect/assets/31014960/9c2787bb-fb00-49d9-8611-80ad7584bda0">

In order to use this feature, you must:
- enable the experimental `Runner` webserver endpoints via
    ```console
    prefect config set PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS=True
    ```
- ensure the `Runner` web server is enabled, either by:
    - passing `webserver=True` to your `serve` call
    - enabling the webserver via
    ```console
    prefect config set PREFECT_RUNNER_SERVER_ENABLE=True
    ```
    
You can then submit any flow available in the import space of the served flow, and you can submit multiple runs at once. If submitting flows from a parent flow, you may optionally block the parent flow run from completing until all submitted runs are complete with `wait_for_submitted_runs()`.

<details>
    <summary>Click for an example</summary>

```python
import time

from pydantic import BaseModel

from prefect import flow, serve, task
from prefect.runner import submit_to_runner, wait_for_submitted_runs


class Foo(BaseModel):
    bar: str
    baz: int


class ParentFoo(BaseModel):
    foo: Foo
    x: int = 42

@task
def noop():
    pass

@flow(log_prints=True)
async def child(foo: Foo = Foo(bar="hello", baz=42)):
    print(f"received {foo.bar} and {foo.baz}")
    print("going to sleep")
    noop()
    time.sleep(20)


@task
def foo():
    time.sleep(2)

@flow(log_prints=True)
def parent(parent_foo: ParentFoo = ParentFoo(foo=Foo(bar="hello", baz=42))):
    print(f"I'm a parent and I received {parent_foo=}")

    submit_to_runner(
        child, [{"foo": Foo(bar="hello", baz=i)} for i in range(9)]
    )
    
    foo.submit()
    
    wait_for_submitted_runs() # optionally block until all submitted runs are complete
    

if __name__ == "__main__":
    # either enable the webserver via `webserver=True` or via
    # `prefect config set PREFECT_RUNNER_SERVER_ENABLE=True`
    serve(parent.to_deployment(__file__), limit=10, webserver=True)
```

</details>

This feature is experimental and subject to change. Please try it out and let us know what you think!

See [the PR](https://github.com/PrefectHQ/prefect/pull/11476) for implementation details.

### Enhancements
- Add `url` to `prefect.runtime.flow_run` — https://github.com/PrefectHQ/prefect/pull/11686
- Add ability to subpath the `/ui-settings` endpoint — https://github.com/PrefectHQ/prefect/pull/11701

### Fixes
- Handle `pydantic` v2 types in schema generation for flow parameters — https://github.com/PrefectHQ/prefect/pull/11656
- Increase flow run resiliency by gracefully handling `PENDING` to `PENDING` state transitions — https://github.com/PrefectHQ/prefect/pull/11695

### Documentation
- Add documentation for `cache_result_in_memory` argument for `flow` decorator — https://github.com/PrefectHQ/prefect/pull/11669
- Add runnable example of `flow.from_source()` — https://github.com/PrefectHQ/prefect/pull/11690
- Improve discoverability of creating interactive workflows guide — https://github.com/PrefectHQ/prefect/pull/11704
- Fix typo in automations guide — https://github.com/PrefectHQ/prefect/pull/11716
- Remove events and incidents from concepts index page — https://github.com/PrefectHQ/prefect/pull/11708
- Remove subflow task tag concurrency warning — https://github.com/PrefectHQ/prefect/pull/11725
- Remove misleading line on pausing a flow run from the UI — https://github.com/PrefectHQ/prefect/pull/11730
- Improve readability of Jinja templating guide in automations concept doc — https://github.com/PrefectHQ/prefect/pull/11729
- Resolve links to relocated interactive workflows guide — https://github.com/PrefectHQ/prefect/pull/11692
- Fix typo in flows concept documentation — https://github.com/PrefectHQ/prefect/pull/11693

### Contributors
- @sgbaird

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.16...2.14.17

## Release 2.14.16

### Support for access block fields in `prefect.yaml` templating

You can now access fields on blocks used in your `prefect.yaml` files. This enables you to use values stored in blocks to provide dynamic configuration for attributes like your `work_pool_name` and `job_variables`.

Here's what it looks like in action:

```yaml
deployments:
- name: test
  version: 0.1
  tags: []
  description: "Example flow"
  schedule: {}
  entrypoint: "flow.py:example_flow"
  parameters: {}
  work_pool:
    name: "{{ prefect.blocks.json.default-config.value.work_pool }}"
    work_queue: "{{ prefect.blocks.json.default-config.value.work_queue }}"
```

In the above example, we use fields from a `JSON` block to configure which work pool and queue we deploy our flow to. We can update where our flow is deployed to by updating the referenced block without needing to change our `prefect.yaml` at all!

Many thanks to @bjarneschroeder for contributing this functionality! Check out this PR for implementation details: https://github.com/PrefectHQ/prefect/pull/10938

### Enhancements
- Add the `wait_for_flow_run` method to `PrefectClient` to allow waiting for a flow run to complete — https://github.com/PrefectHQ/prefect/pull/11305
- Add a provisioner for `Modal` push work pools — https://github.com/PrefectHQ/prefect/pull/11665
- Expose the `limit` kwarg in `serve` to increase its visibility — https://github.com/PrefectHQ/prefect/pull/11645
- Add methods supporting modification and suppression of flow run notification policies — https://github.com/PrefectHQ/prefect/pull/11163
- Enhancements to sending and receiving flow run inputs by automatically converting types to `RunInput` subclasses — https://github.com/PrefectHQ/prefect/pull/11636

### Fixes
- Avoid rerunning task runs forced to `COMPLETED` state — https://github.com/PrefectHQ/prefect/pull/11385
- Add a new UI setting to customize the served static directory — https://github.com/PrefectHQ/prefect/pull/11648

### Documentation
- Fix retry handler example code in task concept docs — https://github.com/PrefectHQ/prefect/pull/11633
- Fix docstring example in `from_source` — https://github.com/PrefectHQ/prefect/pull/11634
- Add an active incident screenshot to the documentation — https://github.com/PrefectHQ/prefect/pull/11647
- Add clarification on work queues being a feature of hybrid work pools only — https://github.com/PrefectHQ/prefect/pull/11651
- Update interactive workflow guide description and heading — https://github.com/PrefectHQ/prefect/pull/11663
- Add API reference documentation for `wait_for_flow_run` — https://github.com/PrefectHQ/prefect/pull/11668
- Remove duplicate line in `prefect deploy` docs — https://github.com/PrefectHQ/prefect/pull/11644
- Update README to clearly mention running the Python file before starting server — https://github.com/PrefectHQ/prefect/pull/11643
- Fix typo in `Modal` infrastructure documentation — https://github.com/PrefectHQ/prefect/pull/11676

## New Contributors
* @N-Demir made their first contribution in https://github.com/PrefectHQ/prefect/pull/11633
* @sgbaird made their first contribution in https://github.com/PrefectHQ/prefect/pull/11644
* @bjarneschroeder made their first contribution in https://github.com/PrefectHQ/prefect/pull/10938
* @Fizzizist made their first contribution in https://github.com/PrefectHQ/prefect/pull/11305
* @NeodarZ made their first contribution in https://github.com/PrefectHQ/prefect/pull/11163

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.15...2.14.16

## Release 2.14.15

### Fixes
- Fix an issue where setting `UI_SERVE_BASE` to an empty string or "/" led to incorrect asset urls - https://github.com/PrefectHQ/prefect/pull/11628

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.14...2.14.15

## Release 2.14.14

## Support for custom prefect.yaml deployment configuration files

You can now specify a `prefect.yaml` deployment configuration file while running `prefect deploy` by using the 
`--prefect-file` command line argument. This means that your configuration files can be in any directory 
and can follow your own naming conventions. Using this feature provides more flexibility in defining 
and managing your deployments.

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11511
- https://github.com/PrefectHQ/prefect/pull/11624

## Toggle Deployment Schedule Status via `prefect.yaml`

You can now toggle your deployment schedules between `active` and `inactive` in your `prefect.yaml` configuration file. This enables you to create deployments with initially _inactive_ schedules, allowing for thorough testing or staged rollouts!

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11608

## Support for Python 3.12

You can now install `prefect` using Python 3.12! This support is experimental and will be hardened in future releases.

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11306

### Enhancements
- Add an option through the CLI and Python client to remove schedules from deployments — https://github.com/PrefectHQ/prefect/pull/11353
- Add client methods to interact with global concurrency limit APIs — https://github.com/PrefectHQ/prefect/pull/11415
- Make `name` optional when saving an existing block — https://github.com/PrefectHQ/prefect/pull/11592
- Make marking a flow as a subflow in `run_deployment`  optional — https://github.com/PrefectHQ/prefect/pull/11611
- Improve IDE support for `PrefectObjectRegistry.register_instances` decorated classes — https://github.com/PrefectHQ/prefect/pull/11617
- Make the UI accessible via reverse proxy and add a `--no-install` flag to `prefect dev build-ui` — https://github.com/PrefectHQ/prefect/pull/11489
- Improve UI build during `prefect server start` - https://github.com/PrefectHQ/prefect/pull/11493
- Improve error message in `.deploy` — https://github.com/PrefectHQ/prefect/pull/11615

### Fixes
- Use default values (if any) when no run input is provided upon `resume` — https://github.com/PrefectHQ/prefect/pull/11598
- Prevent deployments with `RRule` schedules containing `COUNT` — https://github.com/PrefectHQ/prefect/pull/11600
- Fix flows with class-based type hints based on `from __future__ import annotations` — https://github.com/PrefectHQ/prefect/pull/11578 & https://github.com/PrefectHQ/prefect/pull/11616
- Raise `StepExecutionError` on non-zero `run_shell_script` return code during `prefect deploy` — https://github.com/PrefectHQ/prefect/pull/11604

### Experimental
- Enable flow runs to receive typed input from external sources — https://github.com/PrefectHQ/prefect/pull/11573

### Documentation
- Fix non-rendering link in Docker guide — https://github.com/PrefectHQ/prefect/pull/11574
- Update deployment and flow concept docs — https://github.com/PrefectHQ/prefect/pull/11576
- Add examples for custom triggers to automations docs — https://github.com/PrefectHQ/prefect/pull/11589
- Add send/receive documentation to `run_input` module docstring — https://github.com/PrefectHQ/prefect/pull/11591
- Add automations guide — https://github.com/PrefectHQ/prefect/pull/10559
- Fix storage guide links and reference — https://github.com/PrefectHQ/prefect/pull/11602
- Fix typo in `prefect deploy` guide — https://github.com/PrefectHQ/prefect/pull/11606
- Fix imports in human-in-the-loop workflows guide example — https://github.com/PrefectHQ/prefect/pull/11612
- Add missing imports to human-in-the-loop workflows example — https://github.com/PrefectHQ/prefect/pull/11614
- Fix formatting in `prefect deploy` guide — https://github.com/PrefectHQ/prefect/pull/11562
- Remove "Notification blocks must be pre-configured" warning from automations docs — https://github.com/PrefectHQ/prefect/pull/11569
- Update work pools concept docs example to use correct entrypoint — https://github.com/PrefectHQ/prefect/pull/11584
- Add incident, metric, and deployment status info to automations docs - https://github.com/PrefectHQ/prefect/pull/11625

### New Contributors
- @brett-koonce made their first contribution in https://github.com/PrefectHQ/prefect/pull/11562
- @jitvimol made their first contribution in https://github.com/PrefectHQ/prefect/pull/11584
- @oz-elhassid made their first contribution in https://github.com/PrefectHQ/prefect/pull/11353
- @Zyntogz made their first contribution in https://github.com/PrefectHQ/prefect/pull/11415
- @Andrew-S-Rosen made their first contribution in https://github.com/PrefectHQ/prefect/pull/11578

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.13...2.14.14

## Release 2.14.13

## Access default work pool configurations in an air-gapped environment
Those who run Prefect server in an environment where arbitrary outbound internet traffic is not allowed were previously unable to retrieve up-to-date default work pool configurations (via the UI or otherwise). You can now access the worker metadata needed to access the corresponding work pool configurations in your server even in such an air-gapped environment. Upon each release of `prefect`, the most recent version of this worker metadata will be embedded in the `prefect` package so that it can be used as a fallback if the outbound call to retrieve the real-time metadata fails.

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11503

## Introducing conditional task retries for enhanced workflow control
In this release, we're excited to introduce the ability to conditionally retry tasks by passing in an argument to `retry_condition_fn` in your task decorator, enabling more nuanced and flexible retry mechanisms. This adds a significant level of control and efficiency, particularly in handling complex or unpredictable task outcomes. For more information on usage, check out our [docs](https://github.com/PrefectHQ/prefect/pull/11535)!

See the following PR for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11500

### Enhancements
- Add `prefect cloud open` to open current workspace in browser from CLI — https://github.com/PrefectHQ/prefect/pull/11519
- Implement `SendNotification` action type for programmatic Automations — https://github.com/PrefectHQ/prefect/pull/11471
- Display work queue status details via CLI — https://github.com/PrefectHQ/prefect/pull/11545
- Allow users to add date ranges "Around a time" when filtering by date - https://github.com/PrefectHQ/prefect-design/pull/1069

### Fixes
- Validate deployment name in `.deploy` — https://github.com/PrefectHQ/prefect/pull/11539
- Ensure `flow.from_source` handles remote git repository updates — https://github.com/PrefectHQ/prefect/pull/11547

### Documentation
- Add documentation for Incidents feature in Prefect Cloud 
    — https://github.com/PrefectHQ/prefect/pull/11504
    - https://github.com/PrefectHQ/prefect/pull/11532
    - https://github.com/PrefectHQ/prefect/pull/11506
    - https://github.com/PrefectHQ/prefect/pull/11508
- Add security README — https://github.com/PrefectHQ/prefect/pull/11520
- Add conditional pause example to flow documentation — https://github.com/PrefectHQ/prefect/pull/11536
- Add API modules to Python SDK docs — https://github.com/PrefectHQ/prefect/pull/11538
- Update human-in-the-loop documentation — https://github.com/PrefectHQ/prefect/pull/11497
- Improve formatting in quickstart and tutorial — https://github.com/PrefectHQ/prefect/pull/11502
- Fix typo in quickstart — https://github.com/PrefectHQ/prefect/pull/11498
- Fix broken link — https://github.com/PrefectHQ/prefect/pull/11507
- Fix method name typo in tasks tutorial — https://github.com/PrefectHQ/prefect/pull/11523
- Remove redundant word typo — https://github.com/PrefectHQ/prefect/pull/11528

### Collections
- Add `LambdaFunction` block to `prefect-aws` to easily configure and invoke AWS Lambda functions - https://github.com/PrefectHQ/prefect-aws/pull/355

### Contributors
- @yifanmai made their first contribution in https://github.com/PrefectHQ/prefect/pull/11523
- @dominictarro
- @ConstantinoSchillebeeckx

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.12...2.14.13

## Release 2.14.12

### Increased customization of date and time filters across the UI

Building on the enhancements to the dashboard we made in last week's release, we've updated the flow runs page to support relative time spans such as "Past 7 days". These changes make it easier to quickly see what's recently occurred (e.g. "Past 1 hour") and what's coming up next (e.g. "Next 15 minutes"). You can also select and filter by specific date and time ranges. 

We have also updated saved filters on the flow runs page so you can save date ranges as part of a custom filter. For example, it's now possible to create a view of the past 6 hours of runs for a specific work pool!

The Flows page uses the same updated date and time filters so you have more control over how you filter and view runs. 

View a demonstration here: [![short loom video demo](https://github.com/PrefectHQ/prefect/assets/42048900/4dc01ec0-0776-49b4-bbc4-a1472c612e4f)](https://www.loom.com/share/95113969257d4cffa48ad13f943f950f?sid=b20bc27c-0dc2-40be-a627-a2148942c427) 

See the following PRs for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11473
- https://github.com/PrefectHQ/prefect/pull/11481

### Get type-checked input from humans in the loop

Human-in-the-loop flows just got an upgrade. You can now pause or suspend a flow and wait for type-checked input. To get started, declare the structure of the input data using a Pydantic model, and Prefect will render a form dynamically in the UI when a human resumes the flow. Form validation will ensure that the data conforms to your Pydantic model, and your flow will receive the input.

<img width="472" alt="image" src="https://github.com/PrefectHQ/prefect/assets/97182/ac743557-e872-4b48-a61e-c74c95e076f0">

Prefect's new `RunInput` class powers this experience. `RunInput` is a subclass of Pydantic's `BaseModel`. Here's an example of a `RunInput` that uses dates, literals, and nested Pydantic models to show you what's possible:

```python
class Person(RunInput):
    first_name: str
    last_name: str
    birthday: datetime.date
    likes_tofu: bool
    age: int = Field(gt=0, lt=150)
    shirt_size: Literal[ShirtSize.SMALL, ShirtSize.MEDIUM, ShirtSize.LARGE,
                        ShirtSize.XLARGE]
    shirt_color: Literal["red", "blue", "green"]
    preferred_delivery_time: datetime.datetime
    shipping_address: ShippingAddress
    billing_address: BillingAddress | SameAsShipping = Field(
        title="", default_factory=SameAsShipping
    )
```

Check out our [guide on how to create human-in-the-loop flows](https://docs.prefect.io/latest/guides/creating-human-in-the-loop-workflows/) to learn more!

### Enhancements
- Update default pause/suspend timeout to 1 hour — https://github.com/PrefectHQ/prefect/pull/11437

### Fixes
- Resolve environment variables during `prefect deploy` — https://github.com/PrefectHQ/prefect/pull/11463
- Fix prompt and role assignment in `ContainerInstanceProvisioner` — https://github.com/PrefectHQ/prefect/pull/11440
- Ensure dashboard header is responsive to varying tag and date input sizes — https://github.com/PrefectHQ/prefect/pull/11427
- Fix error when deploying a remotely loaded flow with options — https://github.com/PrefectHQ/prefect/pull/11484

### Experimental
- Remove title/description from `RunInput` model — https://github.com/PrefectHQ/prefect/pull/11438

### Documentation
- Add guide to optimizing your code for big data — https://github.com/PrefectHQ/prefect/pull/11225
- Add guide for integrating Prefect with CI/CD via GitHub Actions — https://github.com/PrefectHQ/prefect/pull/11443
- Expand upon managed execution and provisioned infrastructure push work pool in tutorial — https://github.com/PrefectHQ/prefect/pull/11444
- Revise Quickstart to include benefits, remote execution, and core concepts — https://github.com/PrefectHQ/prefect/pull/11461
- Add additions to human-in-the-loop documentation — https://github.com/PrefectHQ/prefect/pull/11487
- Rename guide on reading and writing data to and from cloud provider storage - https://github.com/PrefectHQ/prefect/pull/11441
- Update formatting and work pool docs — https://github.com/PrefectHQ/prefect/pull/11479
- Add documentation for `wait_for_input` — https://github.com/PrefectHQ/prefect/pull/11404
- Fix typo in documentation on`prefect deploy` — https://github.com/PrefectHQ/prefect/pull/11488
- Add troubleshooting instructions for agents — https://github.com/PrefectHQ/prefect/pull/11475
- Update README example and language - https://github.com/PrefectHQ/prefect/pull/11171
- Fix workers graph rendering — https://github.com/PrefectHQ/prefect/pull/11455

### Contributors
- @1beb made their first contribution in https://github.com/PrefectHQ/prefect/pull/11475
- @KMDgit made their first contribution in https://github.com/PrefectHQ/prefect/pull/11488

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.11...2.14.12

## Release 2.14.11

### Customize resource names when provisioning infrastructure for push work pools

In the past few releases, we've added the ability to provision infrastructure for push work pools via the CLI. This release adds the ability to customize the name of the resources created in your cloud environment when provisioning infrastructure for push work pools so you can follow your organization's naming conventions.

To customize your resource names when provisioning infrastructure for a push work pool, follow the interactive prompts:

```bash
? Proceed with infrastructure provisioning with default resource names? [Use arrows to move; enter to select]
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Options:                                                                  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│    │ Yes, proceed with infrastructure provisioning with default resource names │
│ >  │ Customize resource names                                                  │
│    │ Do not proceed with infrastructure provisioning                           │
└────┴───────────────────────────────────────────────────────────────────────────┘
? Please enter a name for the resource group (prefect-aci-push-pool-rg): new-rg
? Please enter a name for the app registration (prefect-aci-push-pool-app): new-app
? Please enter a prefix for the Azure Container Registry (prefect): newregistry
? Please enter a name for the identity (used for ACR access) (prefect-acr-identity): new-identity
? Please enter a name for the ACI credentials block (new-work-pool-push-pool-credentials): new-aci-block
╭───────────────────────────────────────────────────────────────────────────────────────────╮
│ Provisioning infrastructure for your work pool new-work-pool will require:                │
│                                                                                           │
│     Updates in subscription: Azure subscription 1                                         │
│                                                                                           │
│         - Create a resource group in location: eastus                                     │
│         - Create an app registration in Azure AD: new-app                                 │
│         - Create/use a service principal for app registration                             │
│         - Generate a secret for app registration                                          │
│         - Create an Azure Container Registry with prefix newregistry                      │
│         - Create an identity new-identity to allow access to the created registry         │
│         - Assign Contributor role to service account                                      │
│         - Create an ACR registry for image hosting                                        │
│         - Create an identity for Azure Container Instance to allow access to the registry │
│                                                                                           │
│     Updates in Prefect workspace                                                          │
│                                                                                           │
│         - Create Azure Container Instance credentials block: new-aci-block                │
│                                                                                           │
╰───────────────────────────────────────────────────────────────────────────────────────────╯
Proceed with infrastructure provisioning? [y/n]: y
Creating resource group
Resource group 'new-rg' created successfully
Creating app registration
App registration 'new-app' created successfully
Generating secret for app registration
Secret generated for app registration with client ID '03923189-3151-4acd-8d59-76483752cd39'
Creating ACI credentials block
ACI credentials block 'new-aci-block' created in Prefect Cloud
Assigning Contributor role to service account
Service principal created for app ID '25329389-3151-4acd-8d59-71835252cd39'
Contributor role assigned to service principal with object ID '483h4c85-4a8f-4fdb-0394-bd0f0b1202d0'
Creating Azure Container Registry
Registry created
Logged into registry newregistry1702538242q2z2.azurecr.io
Creating identity
Identity 'new-identity' created
Provisioning infrastructure. ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Your default Docker build namespace has been set to 'newregistry1702538242q2z2.azurecr.io'.
Use any image name to build and push to this registry by default:

╭─────────────────────────── example_deploy_script.py ───────────────────────────╮
│ from prefect import flow                                                       │
│ from prefect.deployments import DeploymentImage                                │
│                                                                                │
│                                                                                │
│ @flow(log_prints=True)                                                         │
│ def my_flow(name: str = "world"):                                              │
│     print(f"Hello {name}! I'm a flow running on an Azure Container Instance!") │
│                                                                                │
│                                                                                │
│ if __name__ == "__main__":                                                     │
│     my_flow.deploy(                                                            │
│         name="my-deployment",                                                  │
│         work_pool_name="my-work-pool",                                         │
│         image=DeploymentImage(                                                 │
│             name="my-image:latest",                                            │
│             platform="linux/amd64",                                            │
│         )                                                                      │
│     )                                                                          │
╰────────────────────────────────────────────────────────────────────────────────╯
Infrastructure successfully provisioned for 'new-work-pool' work pool!
Created work pool 'new-work-pool'!
```

Using a push work pool with automatic infrastructure provisioning is a great way to get started with a production-level Prefect set up in minutes! Check out our [push work pool guide](https://docs.prefect.io/latest/guides/deployment/push-work-pools/) for step-by-step instructions on how to get started!

See the following pull requests for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11407
- https://github.com/PrefectHQ/prefect/pull/11381
- https://github.com/PrefectHQ/prefect/pull/11412

### An updated date time input on the workspace dashboard

We've added a new date and time filter to the workspace dashboard that gives greater control over the dashboard. You can now filter by days, hours, and even minutes. You can also specify a specific date and time range to filter by. You can also go backwards and forwards in time using that time window, for example, you can scroll through by hour.  

See it in action!
[![Demo of updated time input in the Prefect UI](https://github.com/PrefectHQ/prefect/assets/40272060/045b144f-35ff-4b32-abcd-74eaf16f181c)
](https://www.loom.com/share/ca099d3792d146d08df6fcd506ff9eb2?sid=70797dda-6dc6-4fe6-bf4a-a9df2a0bf230)

See the following pull requests for implementation details:
- https://github.com/PrefectHQ/prefect-ui-library/pull/1937
- https://github.com/PrefectHQ/prefect-design/pull/1048


### Enhancements
- Add the ability to publish `KubernetesJob` blocks as work pools — https://github.com/PrefectHQ/prefect/pull/11347
- Add setting to configure a default Docker namespace for image builds — https://github.com/PrefectHQ/prefect/pull/11378
- Add the ability to provision an ECR repository for ECS push work pools — https://github.com/PrefectHQ/prefect/pull/11382
- Add ability to provision an Artifact Registry repository for Cloud Run push work pools — https://github.com/PrefectHQ/prefect/pull/11399
- Add ability to provision an Azure Container Registry for Azure Container Instance push work pools — https://github.com/PrefectHQ/prefect/pull/11387
- Add support for `is_schedule_active` to `flow.deploy` and `flow.serve` — https://github.com/PrefectHQ/prefect/pull/11375
- Allow users to select relative and fixed date ranges to filter the dashboard — https://github.com/PrefectHQ/prefect/pull/11406
- Add support for arbitrary sink types to `prefect.utilities.processutils.stream_text` — https://github.com/PrefectHQ/prefect/pull/11298
- Update the Prefect UI deployments page to add run activity and separate out the deployment and flow names — https://github.com/PrefectHQ/prefect/pull/11394  
- Update Prefect UI workspace dashboard filters to use new date range - https://github.com/PrefectHQ/prefect-ui-library/pull/1937

### Fixes
- Fix bug where a pause state reused an existing state ID — https://github.com/PrefectHQ/prefect/pull/11405

### Experimental
- Build out API for creating/reading/deleting flow run inputs — https://github.com/PrefectHQ/prefect/pull/11363
- Integrate flow run input and schema/response mechanics into pause/suspend — https://github.com/PrefectHQ/prefect/pull/11376
- Add typing overloads for pause/suspend methods — https://github.com/PrefectHQ/prefect/pull/11403
- Use bytes for `value` in `create_flow_run_input` — https://github.com/PrefectHQ/prefect/pull/11421
- Validate run input when resuming flow runs — https://github.com/PrefectHQ/prefect/pull/11396
- Run existing deployments via the `Runner` webserver — https://github.com/PrefectHQ/prefect/pull/11333

### Documentation
- Add instructions for automatic infrastructure provisioning to the push work pools guide — https://github.com/PrefectHQ/prefect/pull/11316
- Fix broken links in states concept doc and daemonize guide — https://github.com/PrefectHQ/prefect/pull/11374
- Update agent upgrade guide to include `flow.deploy` and examples — https://github.com/PrefectHQ/prefect/pull/11373
- Update block document names in Moving Data guide  — https://github.com/PrefectHQ/prefect/pull/11386
- Rename `Guides` to` How-to Guides` — https://github.com/PrefectHQ/prefect/pull/11388
- Add guide to provision infrastructure for existing push work pools  — https://github.com/PrefectHQ/prefect/pull/11365
- Add documentation for required permissions for infrastructure provisioning — https://github.com/PrefectHQ/prefect/pull/11417
- Add docs for managed execution open beta — https://github.com/PrefectHQ/prefect/pull/11397, https://github.com/PrefectHQ/prefect/pull/11426, and https://github.com/PrefectHQ/prefect/pull/11425

### Contributors
- @j-tr

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.10...2.14.11

## Release 2.14.10

### Azure Container Instance push pool infrastructure provisioning via the CLI

We're introducing an enhancement to the Azure Container Instance push pool experience. You can now conveniently provision necessary Azure infrastructure with the `--provision-infra` flag during work pool creation, automating the provisioning of various Azure resources essential for ACI push pools, including resource groups, app registrations, service accounts, and more.

To provision Azure resources when creating an ACI push pool:

```bash
❯ prefect work-pool create my-work-pool --provision-infra --type azure-container-instance:push
? Please select which Azure subscription to use: [Use arrows to move; enter to select]
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Name                 ┃ Subscription ID                      ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│    │ Engineering          │ 123                                  │
│ >  │ Azure subscription 1 │ 234                                  │
└────┴──────────────────────┴──────────────────────────────────────┘
╭───────────────────────────────────────────────────────────────────────────────────────╮
│ Provisioning infrastructure for your work pool my-work-pool will require:             │
│                                                                                       │
│     Updates in subscription Azure subscription 1                                      │
│                                                                                       │
│         - Create a resource group in location eastus                                  │
│         - Create an app registration in Azure AD                                      │
│         - Create a service principal for app registration                             │
│         - Generate a secret for app registration                                      │
│         - Assign Contributor role to service account                                  │
│         - Create Azure Container Instance                                             │
│                                                                                       │
│     Updates in Prefect workspace                                                      │
│                                                                                       │
│         - Create Azure Container Instance credentials block aci-push-pool-credentials │
│                                                                                       │
╰───────────────────────────────────────────────────────────────────────────────────────╯
Proceed with infrastructure provisioning? [y/n]: y
Creating resource group
Provisioning infrastructure... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   0% -:--:--Resource group 'prefect-aci-push-pool-rg' created in location 'eastus'
Creating app registration
Provisioning infrastructure... ━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  20% -:--:--App registration 'prefect-aci-push-pool-app' created successfully
Generating secret for app registration
Provisioning infrastructure... ━━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━  40% 0:00:06Secret generated for app registration with client ID 'abc'
ACI credentials block 'aci-push-pool-credentials' created
Assigning Contributor role to service account...
Provisioning infrastructure... ━━━━━━━━━━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━━  60% 0:00:06Contributor role assigned to service principal with object ID 'xyz'
Creating Azure Container Instance
Provisioning infrastructure... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╺━━━━━━━  80% 0:00:04Container instance 'prefect-acipool-container' created successfully
Creating Azure Container Instance credentials block
Provisioning infrastructure... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Infrastructure successfully provisioned for 'my-work-pool' work pool!
Created work pool 'my-work-pool'!
```

This marks a step forward in Prefect's Azure capabilities, offering you an efficient and streamlined process for leveraging Azure Container Instances to execute their workflows.

See the following pull request for implementation details:
— https://github.com/PrefectHQ/prefect/pull/11275

### Introducing the `provision-infra` sub-command for enhanced push work pool management
This enhancement allows you to directly provision infrastructure for existing push work pools. Rather than recreating a work pool, you can provision necessary infrastructure and
update the existing work pool base job template with the following command:

```bash
❯ prefect work-pool provision-infra my-work-pool
? Please select which Azure subscription to use: [Use arrows to move; enter to select]
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Name                 ┃ Subscription ID                      ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│    │ Engineering          │ 13d                                  │
│ >  │ Azure subscription 1 │ 6h4                                  │
└────┴──────────────────────┴──────────────────────────────────────┘
╭────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Provisioning infrastructure for your work pool my-work-pool will require:                                      │
│                                                                                                                │
│     Updates in subscription Azure subscription 1                                                               │
│                                                                                                                │
│         - Create a resource group in location eastus                                                           │
│         - Create an app registration in Azure AD prefect-aci-push-pool-app                                     │
│         - Create/use a service principal for app registration                                                  │
│         - Generate a secret for app registration                                                               │
│         - Assign Contributor role to service account                                                           │
│         - Create Azure Container Instance 'aci-push-pool-container' in resource group prefect-aci-push-pool-rg │
│                                                                                                                │
│     Updates in Prefect workspace                                                                               │
│                                                                                                                │
│         - Create Azure Container Instance credentials block aci-push-pool-credentials                          │
│                                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Proceed with infrastructure provisioning? [y/n]: y
...
```

This PR bolsters support for efficient work pool management across diverse cloud environments, delivering a tool for seamless infrastructure setup.

See the following pull request for implementation details:
- https://github.com/PrefectHQ/prefect/pull/11341
- https://github.com/PrefectHQ/prefect/pull/11355

### Enhancements
- Add a `suspend_flow_run` method to suspend a flow run — https://github.com/PrefectHQ/prefect/pull/11291
- Limit the displayed work pool types when `--provision-infra` is used to only show supported work pool types - https://github.com/PrefectHQ/prefect/pull/11350
- Add the ability to publish `Infrastructure` blocks as work pools — https://github.com/PrefectHQ/prefect/pull/11180
- Add the ability to publish `Process` blocks as work pools — https://github.com/PrefectHQ/prefect/pull/11346
- Add a Prefect Cloud event stream subscriber — https://github.com/PrefectHQ/prefect/pull/11332
- Enable storage of key/value information associated with a flow run — https://github.com/PrefectHQ/prefect/pull/11342
- Delete flow run inputs when the corresponding flow run is delete — https://github.com/PrefectHQ/prefect/pull/11352

### Fixes
- Fix the `read_logs` return type to be `List[Log]` — https://github.com/PrefectHQ/prefect/pull/11303
- Fix an issue causing paused flow runs to become stuck in the `Paused` state — https://github.com/PrefectHQ/prefect/pull/11284

### Documentation
- Combine troubleshooting pages — https://github.com/PrefectHQ/prefect/pull/11288
- Add Google Cloud Run V2 option to Serverless guide — https://github.com/PrefectHQ/prefect/pull/11304
- Add `suspend_flow_run` to flows documentation — https://github.com/PrefectHQ/prefect/pull/11300
- Add `work queues` tag to work pools concept page — https://github.com/PrefectHQ/prefect/pull/11320
- Add missing Python SDK CLI items to the docs — https://github.com/PrefectHQ/prefect/pull/11289
- Clarify SCIM + service accounts handling — https://github.com/PrefectHQ/prefect/pull/11343
- Update the work pool concept document — https://github.com/PrefectHQ/prefect/pull/11331

### Contributors
- @tekumara

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.9...2.14.10

## Release 2.14.9

### Automatic infrastructure provisioning for ECS push work pools

Following the introduction of [automatic project configuration for Cloud Run push pools](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md#automatic-project-configuration-for-cloud-run-push-work-pools) last week, we've added the ability to automatically provision infrastructure in your AWS account and set up your Prefect workspace to support a new ECS push pool!

You can create a new ECS push work pool and provision infrastructure in your AWS account with the following command:

```bash
prefect work-pool create --type ecs:push --provision-infra my-pool 
```

Using the `--provision-infra` flag will automatically set up your default AWS account to be ready to execute flows via ECS tasks:

```
╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Provisioning infrastructure for your work pool my-work-pool will require:                                         │
│                                                                                                                   │
│          - Creating an IAM user for managing ECS tasks: prefect-ecs-user                                          │
│          - Creating and attaching an IAM policy for managing ECS tasks: prefect-ecs-policy                        │
│          - Storing generated AWS credentials in a block                                                           │
│          - Creating an ECS cluster for running Prefect flows: prefect-ecs-cluster                                 │
│          - Creating a VPC with CIDR 172.31.0.0/16 for running ECS tasks: prefect-ecs-vpc                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Proceed with infrastructure provisioning? [y/n]: y
Provisioning IAM user
Creating IAM policy
Generating AWS credentials
Creating AWS credentials block
Provisioning ECS cluster
Provisioning VPC
Creating internet gateway
Setting up subnets
Setting up security group
Provisioning Infrastructure ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Infrastructure successfully provisioned!
Created work pool 'my-pool'!
```

If you have yet to try using an ECS push pool, now is a great time!

If you use Azure, don't fret; we will add support for Azure Container Instances push work pools in a future release!

See the following pull request for implementation details:
— https://github.com/PrefectHQ/prefect/pull/11267


### Enhancements
- Make flows list on Flows page in the Prefect UI a scannable table — https://github.com/PrefectHQ/prefect/pull/11274

### Fixes
- Fix `.serve` crashes due to process limiter — https://github.com/PrefectHQ/prefect/pull/11264
- Fix URL formatting in `GitRepository` when using provider-specific git credentials blocks — https://github.com/PrefectHQ/prefect/pull/11282
- Prevent excessively escaping the Windows executable — https://github.com/PrefectHQ/prefect/pull/11253

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.8...2.14.9

## Release 2.14.8

This release is a follow-up to 2.14.7 which never made it to PyPI because of an issue with our Github workflow. 

### Documentation
- Fix broken docs link in serverless worker documentation — https://github.com/PrefectHQ/prefect/pull/11269

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.14.7...2.14.8

## Release 2.14.7

This release fixes a bug introduced in 2.14.6 where deployments with default Docker image builds looked for images tagged `v2.14.6` instead of `2.14.6`. Users of `2.14.6` should upgrade if planning to create deployments with an image other than a custom image.

### Enhancements

- Use a new route to read work pool types when connected to Prefect Cloud — <https://github.com/PrefectHQ/prefect/pull/11236>
- Add `parent_flow_run_id` as a new API filter for flow runs — <https://github.com/PrefectHQ/prefect/pull/11089>

### Fixes

- Allow more than one dependency package in the requirements of a push or pull step — <https://github.com/PrefectHQ/prefect/pull/11254>

### Documentation

- Add serverless work pool landing page — <https://github.com/PrefectHQ/prefect/pull/11004>
- Update Azure Container Instance guide to reflect current Azure Portal interface and Prefect UI — <https://github.com/PrefectHQ/prefect/pull/11256>
- Update imports in **Flows** concept page example — <https://github.com/PrefectHQ/prefect/pull/11235>

### New Contributors

- @oakbramble made their first contribution in <https://github.com/PrefectHQ/prefect/pull/11089>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.6...2.14.7>

## Release 2.14.6

### View the next run for a deployment at a glance

You can now see the next run for a deployment in the Runs tab of the Deployments page in the Prefect UI! Upcoming runs are now located in a dedicated tab, making the most relevant running and completed flow runs more apparent.

Click below to see it in action!
[![Demo of next run for a deployment](https://github.com/PrefectHQ/prefect/assets/12350579/c6eee55a-c3c3-47bd-b2c1-9eb04139a376)
](https://github.com/PrefectHQ/prefect/assets/12350579/c1658f50-512a-4cd4-9d36-a523d3cc9ef0)

See the following pull request for implementation details:
— <https://github.com/PrefectHQ/prefect/pull/11230>

### Automatic project configuration for Cloud Run push work pools

Push work pools in Prefect Cloud simplify the setup and management of the infrastructure necessary to run your flows, but they still require some setup. With this release, we've enhanced the `prefect work-pool create` CLI command to automatically configure your GCP project and set up your Prefect workspace to use a new Cloud Run push pool immediately.

Note: To take advantage of this feature, you'll need to have the `gcloud` CLI installed and authenticated with your GCP project.

You can create a new Cloud Run push work pool and configure your project with the following command:

```bash
prefect work-pool create --type cloud-run:push --provision-infra my-pool 
```

Using the `--provision-infra` flag will allow you to select a GCP project to use for your work pool and automatically configure it to be ready to execute flows via Cloud Run:

```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Provisioning infrastructure for your work pool my-pool will require:                                     │
│                                                                                                          │
│     Updates in GCP project central-kit-405415 in region us-central1                                      │
│                                                                                                          │
│         - Activate the Cloud Run API for your project                                                    │
│         - Create a service account for managing Cloud Run jobs: prefect-cloud-run                        │
│             - Service account will be granted the following roles:                                       │
│                 - Service Account User                                                                   │
│                 - Cloud Run Developer                                                                    │
│         - Create a key for service account prefect-cloud-run                                             │
│                                                                                                          │
│     Updates in Prefect workspace                                                                         │
│                                                                                                          │
│         - Create GCP credentials block my--pool-push-pool-credentials to store the service account key   │
│                                                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Proceed with infrastructure provisioning? [y/n]: y
Activating Cloud Run API
Creating service account
Assigning roles to service account
Creating service account key
Creating GCP credentials block
Provisioning Infrastructure ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Infrastructure successfully provisioned!
Created work pool 'my-pool'!
```

If you have yet to try using a Cloud Run run push pool, now is a great time!

If you use another cloud provider, don't fret; we will add support for ECS and Azure Container Instances push work pools in future releases!

See the following pull request for implementation details:
— <https://github.com/PrefectHQ/prefect/pull/11204>

### Enhancements

- Add ability to search for block documents by name in the Prefect UI and API — <https://github.com/PrefectHQ/prefect/pull/11212>
- Add pagination to the Blocks page in the Prefect UI for viewing/filtering more than 200 blocks — <https://github.com/PrefectHQ/prefect/pull/11214>
- Include concurrency controls in `prefect-client` — <https://github.com/PrefectHQ/prefect/pull/11227>

### Fixes

- Fix SQLite migration to work with older SQLite versions — <https://github.com/PrefectHQ/prefect/pull/11215>
- Fix Subflow Runs tab filters and persist to URL in the Flow Runs page of the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/11218>

### Documentation

- Improve formatting in deployment guides — <https://github.com/PrefectHQ/prefect/pull/11217>
- Add instructions for turning off the flow run logger to the unit testing guide — <https://github.com/PrefectHQ/prefect/pull/11223>

### Contributors

- @ConstantinoSchillebeeckx

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.5...2.14.6>

## Release 2.14.5

### Storage block compatibility with `flow.from_source`

You can now use all your existing storage blocks with `flow.from_source`! Using storage blocks with `from_source` is great when you need to synchronize your credentials and configuration for your code storage location with your flow run execution environments. Plus, because block configuration is stored server-side and pulled at execution time, you can update your code storage credentials and configuration without re-deploying your flows!

Here's an example of loading a flow from a private S3 bucket and serving it:

```python
from prefect import flow
from prefect_aws import AwsCredentials
from prefect_aws.s3 import S3Bucket

if __name__ == "__main__":
    flow.from_source(
        source=S3Bucket(
            bucket_name="my-code-storage-bucket",
            credentials=AwsCredentials(
                aws_access_key_id="my-access-key-id",
                aws_secret_access_key="my-secret-access-key",
            ),
        ),
        entrypoint="flows.py:my_flow",
    ).serve(name="my-deployment")
```

Here's an example of loading and deploying a flow from an S3 bucket:

```python
from prefect import flow
from prefect_aws.s3 import S3Bucket

if __name__ == "__main__":
    flow.from_source(
        source=S3Bucket.load("my-code-storage-bucket"), entrypoint="flows.py:my_flow"
    ).deploy(name="my-deployment", work_pool_name="above-ground")
```

Note that a storage block must be saved before deploying a flow, but not if you're serving a remotely stored flow.

See the following pull request for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/11092>

### Enhancements

- Add customizable host and port settings for worker webserver — <https://github.com/PrefectHQ/prefect/pull/11175>
- Safely retrieve `flow_run_id` in `EventsWorker` while finding related events — <https://github.com/PrefectHQ/prefect/pull/11182>
- Add client-side setting for specifying a default work pool — <https://github.com/PrefectHQ/prefect/pull/11137>
- Allow configuration of task run tag concurrency slot delay transition time via setting — <https://github.com/PrefectHQ/prefect/pull/11020>
- Enable enhanced flow run cancellation by default - <https://github.com/PrefectHQ/prefect/pull/11192>

### Fixes

- Fix access token retrieval when using `GitRepository` with a private repo and `.deploy` — <https://github.com/PrefectHQ/prefect/pull/11156>
- Fix bug where check for required packages fails incorrectly during `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/11111>
- Fix routing to the Flows page from a flow run in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/11190>
- Ensure the Prefect UI Flow Runs page reacts to filter changes - <https://github.com/PrefectHQ/prefect-ui-library/pull/1874>
- Optimize memory usage by clearing `args/kwargs` in a Prefect `Call` post-execution -  <https://github.com/PrefectHQ/prefect/pull/11153>
- Allow logs to handle un-`uuid`-like flow_run_ids - <https://github.com/PrefectHQ/prefect/pull/11191>
- Only run unit tests for Python file changes — <https://github.com/PrefectHQ/prefect/pull/11159>
- Add `codespell` config and add to pre-commit  — <https://github.com/PrefectHQ/prefect/pull/10893>
- Update token regex in release notes generation script for VSCode compatibility - <https://github.com/PrefectHQ/prefect/pull/11195>

### Documentation

- Add Terraform Provider guide, update and simplify guides navigation — <https://github.com/PrefectHQ/prefect/pull/11170>
- Clarify and harmonize Prefect Cloud documentation to reflect nomenclature and UX changes — <https://github.com/PrefectHQ/prefect/pull/11157>
- Add information on Prefect Cloud to README — <https://github.com/PrefectHQ/prefect/pull/11167>
- Update work pool-based deployment guide to include `.deploy` — <https://github.com/PrefectHQ/prefect/pull/11174>
- Add Github information to auth-related Prefect Cloud documentation — <https://github.com/PrefectHQ/prefect/pull/11178>
- Update workers tutorial — <https://github.com/PrefectHQ/prefect/pull/11185>
- Update mkdocs material pin — <https://github.com/PrefectHQ/prefect/pull/11160>
- Fix typo in audit log documentation — <https://github.com/PrefectHQ/prefect/pull/11161>
- Fix typo in workers tutorial example — <https://github.com/PrefectHQ/prefect/pull/11183>

### Contributors

- @yarikoptic made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10893>
- @taljaards

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.4...2.14.5>

## Release 2.14.4

### New improved flow run graph with dependency layout

The flow run graph in the Prefect UI has been rebuilt from the ground up, offering significantly improved performance capabilities that allow larger flow runs to be displayed much more smoothly. We’ve added three new layouts: two non-temporal layout options, designed to provide a clearer picture of the dependency paths, and one to facilitate easy comparison of run durations. The x-axis can now be independently scaled for temporal layouts; and you can adjust it in the graph settings or with the new keyboard shortcuts - and +. We included additional small bug fixes, including the display of cached tasks.

<p align="center">
<img width="976" alt="flow run graph sequential grid view" src="https://user-images.githubusercontent.com/6776415/281769376-bccc4cd5-db2c-42b9-9c21-fc32b094323b.png">
</p>

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/11112>
- <https://github.com/PrefectHQ/prefect/pull/11105>
- <https://github.com/PrefectHQ/prefect/pull/11113>
- <https://github.com/PrefectHQ/prefect/pull/11132>
- <https://github.com/PrefectHQ/prefect/pull/11138>

### Enhancements

- Add API route for block counts — <https://github.com/PrefectHQ/prefect/pull/11090>
- Improved tag handling on `DeploymentImage` for `.deploy`:
  - <https://github.com/PrefectHQ/prefect/pull/11115>
  - <https://github.com/PrefectHQ/prefect/pull/11119>
- Allow `image` passed into `.deploy` to be optional if loading flow from storage — <https://github.com/PrefectHQ/prefect/pull/11117>
- Ensure client avoids image builds when deploying to managed work pools — <https://github.com/PrefectHQ/prefect/pull/11120>
- Add `SIGTERM` handling to runner to gracefully handle timeouts — <https://github.com/PrefectHQ/prefect/pull/11133>
- Allow tasks to use `get_run_logger` w/o parent flow run — <https://github.com/PrefectHQ/prefect/pull/11129>
- Allow `ResultFactory` creation `from_task` when no `flow_run_context` — <https://github.com/PrefectHQ/prefect/pull/11134>

### Fixes

- Avoid printing references to workers when deploying to managed pools — <https://github.com/PrefectHQ/prefect/pull/11122>

### Documentation

- Fix docstring for `flow.deploy` method example — <https://github.com/PrefectHQ/prefect/pull/11108>
- Add warning about image architecture to push pool guide — <https://github.com/PrefectHQ/prefect/pull/11118>
- Move webhooks guide to `Development` section in guides index — <https://github.com/PrefectHQ/prefect/pull/11141>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.3...2.14.4>

## Release 2.14.3

### Observability with deployment status

You can now track the status of your deployments in the Prefect UI, which is especially useful when serving flows as they have no associated work pool or worker. If you see a flow run enter a `LATE` state (it isn’t running), you can click into the deployment for that flow run and see a red indicator next to your deployment. The worker, runner, or agent polling that deployment or its associated work queue is offline.

- Deployments created from served flows will have a `READY` status if its associated process is running.
- Deployments created in a work pool will have a `READY` status when a worker is `ONLINE` and polling the associated work queue.
- Deployments created in a push work pool (Prefect Cloud) will always have a `READY` status.
  
<p align="center">
<img width="976" alt="a late flow run for a deployment that is `NOT_READY`" src="https://github.com/PrefectHQ/prefect/assets/42048900/db20979a-870d-44c4-ac0b-66f70d99e58b">
</p>

In Prefect Cloud, an event is emitted each time a deployment changes status. These events are viewable in the Event Feed.
<p align="center">
<img width="538" alt="event feed deployment status events" src="https://github.com/PrefectHQ/prefect/assets/42048900/8ee076cd-fd30-47d1-9ee5-6b5a3b383b63">
</p>

You can also create an automation triggered by deployment status changes on the Automations page!

<p align="center">
<img width="862" alt="deployment status trigger on automations page" src="https://github.com/PrefectHQ/prefect/assets/42048900/87a0945e-9b9e-406b-b020-fbd9733cb4c3">
</p>

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect-ui-library/pull/1801>
- <https://github.com/PrefectHQ/prefect/pull/10969>
- <https://github.com/PrefectHQ/prefect/pull/10951>
- <https://github.com/PrefectHQ/prefect/pull/10949>

### Additional storage options for `flow.from_source`

You can now load flows from a variety of storage options with `flow.from_source`! In addition to loading flows from a git repository, you can load flows from any supported `fsspec` protocol.

Here's an example of loading and serving a flow from an S3 bucket:

```python
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
        source="s3://my-bucket/my-folder",
        entrypoint="flows.py:my_flow",
    ).serve(name="deployment-from-remote-flow")
```

You can use the `RemoteStorage` class to provide additional configuration options.

Here's an example of loading and serving a flow from Azure Blob Storage with a custom account name:

```python
from prefect import flow
from prefect.runner.storage import RemoteStorage

if __name__ == "__main__":
    flow.from_source(
        source=RemoteStorage(url="az://my-container/my-folder", account_name="my-account-name"),
        entrypoint="flows.py:my_flow",
    ).serve(name="deployment-from-remote-flow")
```

See the following pull request for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/11072>

### Enhancements

- Add option to skip building a Docker image with `flow.deploy` — <https://github.com/PrefectHQ/prefect/pull/11082>
- Display placeholder on the variables page when no variables are present — <https://github.com/PrefectHQ/prefect/pull/11044>
- Allow composite sort of block documents by `block_type_name` and name — <https://github.com/PrefectHQ/prefect/pull/11054>
- Add option to configure a warning via `PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD` if task parameter introspection takes a long time — <https://github.com/PrefectHQ/prefect/pull/11075>

### Fixes

- Update cancellation cleanup service to allow for infrastructure teardown — <https://github.com/PrefectHQ/prefect/pull/11055>
- Allow `password` to be provided in `credentials` for `GitRespository` — <https://github.com/PrefectHQ/prefect/pull/11056>
- Enable page refresh loading for non dashboard pages — <https://github.com/PrefectHQ/prefect/pull/11065>
- Allow runner to load remotely stored flows when running hooks — <https://github.com/PrefectHQ/prefect/pull/11077>
- Fix reading of flow run graph with unstarted runs — <https://github.com/PrefectHQ/prefect/pull/11070>
- Allow Pydantic V2 models in flow function signatures — <https://github.com/PrefectHQ/prefect/pull/10966>
- Run `prefect-client` build workflow on reqs.txt updates — <https://github.com/PrefectHQ/prefect/pull/11079>
- Skips unsupported Windows tests — <https://github.com/PrefectHQ/prefect/pull/11076>
- Avoid yanked `pytest-asyncio==0.22.0` — <https://github.com/PrefectHQ/prefect/pull/11064>

### Documentation

- Add guide to daemonize a worker or `.serve` process with systemd — <https://github.com/PrefectHQ/prefect/pull/11008>
- Add clarification of term `task` in Global Concurrency docs — <https://github.com/PrefectHQ/prefect/pull/11085>
- Update Global Concurrency guide to highlight general purpose use of concurrency limits — <https://github.com/PrefectHQ/prefect/pull/11074>
- Update push work pools documentation to mention concurrency — <https://github.com/PrefectHQ/prefect/pull/11068>
- Add documentation on Prefect Cloud teams — <https://github.com/PrefectHQ/prefect/pull/11057>
- Update 2.14.2 release notes  — <https://github.com/PrefectHQ/prefect/pull/11053>
- Fix rendering of marketing banner on the Prefect dashboard — <https://github.com/PrefectHQ/prefect/pull/11069>
- Fix typo in `README.md` — <https://github.com/PrefectHQ/prefect/pull/11058>

## New Contributors

- @vatsalya-vyas made their first contribution in <https://github.com/PrefectHQ/prefect/pull/11058>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.2...2.14.3>

## Release 2.14.2

### Ability to pass **kwargs to state change hooks

You can now pass a partial (sometimes called ["curried"](https://www.geeksforgeeks.org/partial-functions-python/)) hook to your tasks and flows, allowing for more tailored post-execution behavior.

```python
from functools import partial
from prefect import flow

data = {}

def my_hook(flow, flow_run, state, **kwargs):
    data.update(state=state, **kwargs)

@flow(on_completion=[partial(my_hook, my_arg="custom_value")])
def lazy_flow():
    pass

state = lazy_flow(return_state=True)

assert data == {"my_arg": "custom_value", "state": state}
```

This can be used in conjunction with the `.with_options` method on tasks and flows to dynamically provide extra kwargs to your hooks, like [this example](https://docs.prefect.io/latest/concepts/states/#pass-kwargs-to-your-hooks) in the docs.

See the following pull request for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/11022>

### Fixes

- Moves responsibility for running `on_cancellation` and `on_crashed` flow hooks to runner when present — <https://github.com/PrefectHQ/prefect/pull/11026>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.1...2.14.2>

## Release 2.14.1

### Documentation

- Add Python `serve` and `deploy` options to the `schedules` concepts documentation — <https://github.com/PrefectHQ/prefect/pull/11000>

### Fixes

- Refine flow parameter validation to use the correct form of validation depending on if the parameter is a pydantic v1 or v2 model.  — <https://github.com/PrefectHQ/prefect/pull/11028>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.14.0...2.14.1>

## Release 2.14.0

### Introducing the `prefect-client`

This release provides a new way of running flows using the `prefect-client` package. This slimmed down version of `prefect` has a small surface area of functionality and is intended for interacting with the Prefect server or Prefect Cloud **only**. You can install `prefect-client` by using `pip`:

```bash
pip install prefect-client
```

To use it, you will need to configure your environment to interact with a remote Prefect API by setting the `PREFECT_API_URL` and `PREFECT_API_KEY` environment variables. Using it in your code remains the same:

```python
from prefect import flow, task

@flow(log_prints=True)
def hello_world():
    print("Hello from prefect-client!")

hello_world()
```

See implementation details in the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10988>

### Enhancements

- Add flow name to the label for subflow runs in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/11009>

### Fixes

- Fix ability to pull flows and build deployments in Windows environments - <https://github.com/PrefectHQ/prefect/pull/10989>
- Remove unnecessary work queue health indicator from push pools in the Prefect UI dashboard - <https://github.com/PrefectHQ/prefect-ui-library/pull/1813>
- Rename mismatched alembic file — <https://github.com/PrefectHQ/prefect/pull/10888>

### Documentation

- Standardize heading capitalization in guide to developing a new worker type — <https://github.com/PrefectHQ/prefect/pull/10999>
- Update Docker guide to mention image builds with `prefect.yaml` and `flow.deploy` — <https://github.com/PrefectHQ/prefect/pull/11012>
- Update Kubernetes guide to mention and link to Python-based flow `deploy` creation method — <https://github.com/PrefectHQ/prefect/pull/11010>

## New Contributors

- @m-steinhauer made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10888>

- @maitlandmarshall made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10989>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.8...2.14.0>

## Release 2.13.8

### Introducing `flow.deploy`

When we released `flow.serve`, we introduced a radically simple way to deploy flows. Serving flows is perfect for many use cases, but the need for persistent infrastructure means serving flows may not work well for flows that require expensive or limited infrastructure.

We're excited to introduce `flow.deploy` as a simple transition from running your served flows on persistent infrastructure to executing your flows on dynamically provisioned infrastructure via work pools and workers. `flow.deploy` ensures your flows execute consistently across environments by packaging your flow into a Docker image and making that image available to your workers when executing your flow.

Updating your serve script to a deploy script is as simple as changing `serve` to `deploy`, providing a work pool to deploy to, and providing a name for the built image.

Here's an example of a serve script:

```python
from prefect import flow


@flow(log_prints=True)
def hello_world(name: str = "world", goodbye: bool = False):
    print(f"Hello {name} from Prefect! 🤗")

    if goodbye:
        print(f"Goodbye {name}!")


if __name__ == "__main__":
    hello_world.serve(
        name="my-first-deployment",
        tags=["onboarding"],
        parameters={"goodbye": True},
        interval=60,
    )
```

transitioned to a deploy script:

```python
from prefect import flow


@flow(log_prints=True)
def hello_world(name: str = "world", goodbye: bool = False):
    print(f"Hello {name} from Prefect! 🤗")

    if goodbye:
        print(f"Goodbye {name}!")


if __name__ == "__main__":
    hello_world.deploy(
        name="my-first-deployment",
        tags=["onboarding"],
        parameters={"goodbye": True},
        interval=60,
        work_pool_name="above-ground",
        image='my_registry/hello_world:demo'
    )
```

You can also use `deploy` as a replacement for `serve` if you want to deploy multiple flows at once.

For more information, check out our tutorial's newly updated [Worker & Work Pools](https://docs.prefect.io/latest/tutorial/workers/) section!

See implementation details in the following pull requests:

- <https://github.com/PrefectHQ/prefect/pull/10957>
- <https://github.com/PrefectHQ/prefect/pull/10975>
- <https://github.com/PrefectHQ/prefect/pull/10993>

### Enhancements

- Add `last_polled` column to deployment table — <https://github.com/PrefectHQ/prefect/pull/10949>
- Add `status` and `last_polled` to deployment API responses — <https://github.com/PrefectHQ/prefect/pull/10951>
- Add flow run graph v2 endpoint tuned for UI applications — <https://github.com/PrefectHQ/prefect/pull/10912>
- Add ability to convert `GitRepository` into `git_clone` deployment step — <https://github.com/PrefectHQ/prefect/pull/10957>
- Update `/deployments/get_scheduled_flow_runs` endpoint to update deployment status — <https://github.com/PrefectHQ/prefect/pull/10969>

### Fixes

- Clarify CLI prompt message for missing integration library for worker — <https://github.com/PrefectHQ/prefect/pull/10990>
- Renamed `ruamel-yaml` to `ruamel.yaml` in `requirements.txt` — <https://github.com/PrefectHQ/prefect/pull/10987>
- Clarify work pool banner on Work Pool page UI — <https://github.com/PrefectHQ/prefect/pull/10992>

### Documentation

- Clean up `Using the Prefect Orchestration Client` guide — <https://github.com/PrefectHQ/prefect/pull/10968>
- Add link to Coiled's documentation for hosting served flows — <https://github.com/PrefectHQ/prefect/pull/10977>
- Clarify that access control lists do not affect related objects  — <https://github.com/PrefectHQ/prefect/pull/10934>
- Improve block-based deployment concept page metadata and admonitions — <https://github.com/PrefectHQ/prefect/pull/10970>
- Update docs to prioritize workers over agents — <https://github.com/PrefectHQ/prefect/pull/10904>
- Update work pools and workers tutorial to use `flow.deploy` — <https://github.com/PrefectHQ/prefect/pull/10985>
- Move Docker image discussion to Docker guide — <https://github.com/PrefectHQ/prefect/pull/10910>

### Contributors

- @lpequignot made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10987>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.7...2.13.8>

## Release 2.13.7

### Enabling Pydantic V2

In 2.13.5 we released experimental support for Pydantic V2, which made it co-installable via forced install. In this release, we are enabling co-installation by default which will allow you to leverage Pydantic V2 in your flows and tasks. Additionally, you can choose to update to Pydantic V2 on your own timeline as we maintain compatibility with V1 within flows and tasks.

See implementation details in the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10946>

### Documentation

- Fix typo in release notes - <https://github.com/PrefectHQ/prefect/pull/10950>

### Contributors

- @taljaards

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.6...2.13.7>

## Release 2.13.6

### Specify a default result storage block as a setting

Previously, specifying result storage blocks necessitated changes in the `@flow` or `@task` decorator. Now, the `PREFECT_DEFAULT_RESULT_STORAGE_BLOCK` setting allows users to set a default storage block on a work pool or via job variables for a deployment. For example, to set a default storage block for a deployment via `prefect.yaml`:

```yaml
deployments:
- name: my-super-cool-deployment
  entrypoint: some_directory/some_file.py:my_flow
  schedule:
    cron: "0 20 * * 1-5"
  work_pool:
    name: ecs-pool
    job_variables:
      env:
        PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: s3/my-s3-bucket-block-name
```

This enhancement enables easier swapping of result storages by just updating the environment in the UI or in your `prefect.yaml`, eliminating the need to alter your flow source code.

See the following pull request for details:

- <https://github.com/PrefectHQ/prefect/pull/10925>

### Experimental support for enhanced cancellation

We're introducing a new experimental feature that will enable more consistent and reliable cancellation of flow runs.

To enable enhanced cancellation, set the `PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION` setting on your worker or agents to `True`:

```bash
prefect config set PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION=True
```

When enabled, you can cancel flow runs where cancellation can fail, such as when your worker is offline. We will continue to develop enhanced cancellation to improve its reliability and performance. If you encounter any issues, please let us know in Slack or with a Github issue.

Note: If you are using the Kubernetes worker, you will need to update your `prefect-kubernetes` installation to `0.3.1`. If you are using the Cloud Run or Vertex AI workers, you will need to update your `prefect-gcp` installation to `0.5.1`.

See the following pull requests for details:

- <https://github.com/PrefectHQ/prefect/pull/10920>
- <https://github.com/PrefectHQ/prefect/pull/10944>

### Enhancements

- Add link to Prefect Cloud information in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/10909>

### Fixes

- Avoid `prefect deploy` prompt for remote storage if a global pull step is already defined - <https://github.com/PrefectHQ/prefect/pull/10941>

### Documentation

- Add a guide for using the Prefect client — <https://github.com/PrefectHQ/prefect/pull/10924>
- Remove icons from side navigation for improved readability — <https://github.com/PrefectHQ/prefect/pull/10908>
- Update deployments tutorial for consistent styling — <https://github.com/PrefectHQ/prefect/pull/10911>
- Fix typo in CLI command in deployments tutorial — <https://github.com/PrefectHQ/prefect/pull/10937>
- Fix typo in logging guide — <https://github.com/PrefectHQ/prefect/pull/10936>
- Update documentation styling  — <https://github.com/PrefectHQ/prefect/pull/10913>

### Contributors

- @Sun-of-a-beach made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10937>

- @manaw

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.5...2.13.6>

## Release 2.13.5

### Load and serve remotely stored flows

You can now load and serve flows from a git repository!

With the new `flow.from_source` method, you can specify a git repository and a path to a flow file in that repository. This method will return a flow object that can be run or served with `flow.serve()`.

Here's an example of loading a flow from a git repository and serving it:

```python
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/org/repo.git",
        entrypoint="path/to/flow.py:my_flow",
    ).serve(name="deployment-from-remote-flow")
```

When you load and serve a flow from a git repository, the serving process will periodically poll the repository for changes. This means that you can update the flow in the repository and the changes will be reflected in the served flow without restarting the serve script!

To learn more about loading and serving flows from a git repository, check out [the docs](https://docs.prefect.io/latest/concepts/flows/#retrieve-a-flow-from-remote-storage)!

See the following pull requests for details:

- <https://github.com/PrefectHQ/prefect/pull/10884>
- <https://github.com/PrefectHQ/prefect/pull/10850>

### Experimental Pydantic 2 Compatibility

We're working eagerly toward having `prefect` installable with either `pydantic<2` or `pydantic>2`.  As a first step toward compatibility, we've ensured that Prefect's use of `pydantic` is isolated from _your_ use of `pydantic` in as many ways as possible.  As of this release, `prefect` still has a stated `pydantic` requirement of `<2`, but we are testing against `pydantic>2` in our continuous integration tests.  If you're feeling adventurous, feel free to manually install `pydantic>2` and run some flows with it.  If you do, please let us know how it's going with a note in Slack or with a Github issue.

See the following pull requests for details

- <https://github.com/PrefectHQ/prefect/pull/10860>
- <https://github.com/PrefectHQ/prefect/pull/10867>
- <https://github.com/PrefectHQ/prefect/pull/10868>
- <https://github.com/PrefectHQ/prefect/pull/10870>
- <https://github.com/PrefectHQ/prefect/pull/10873>
- <https://github.com/PrefectHQ/prefect/pull/10891>
- <https://github.com/PrefectHQ/prefect/pull/10876>

### Enhancements

- Use flow run context for default values in task run logger — <https://github.com/PrefectHQ/prefect/pull/10334>
- Default `PREFECT_UI_API_URL` to relative path /api — <https://github.com/PrefectHQ/prefect/pull/10755>
- Add blob storage options to `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10656>
- Add retries on responses with a 408 status code — <https://github.com/PrefectHQ/prefect/pull/10883>

### Fixes

- Ensure agents only query work queues in `default-agent-pool`  work pool if no pool is specified — <https://github.com/PrefectHQ/prefect/pull/10804>
- Update `Runner` to correctly handle spaces in Python executable path — <https://github.com/PrefectHQ/prefect/pull/10878>
- Update `PREFECT__FLOW_RUN_ID` environment variable to dash-delimited UUID format — <https://github.com/PrefectHQ/prefect/pull/10881>
- Fix bug preventing importing `prefect` in a thread — <https://github.com/PrefectHQ/prefect/pull/10871>

### Documentation

- Add GCP Vertex AI worker to worker types list in work pools documentation — <https://github.com/PrefectHQ/prefect/pull/10858>
- Expound upon rate limit info and global concurrency use cases in concurrency guide — <https://github.com/PrefectHQ/prefect/pull/10886>
- Point docker guide link to tutorial on workers — <https://github.com/PrefectHQ/prefect/pull/10872>
- Clarify workers and work pools as an alternative to `.serve()` in tutorials — <https://github.com/PrefectHQ/prefect/pull/10861>
- Fix typo in deployments concept page — <https://github.com/PrefectHQ/prefect/pull/10857>
- Remove beta label from push work pool documentation — <https://github.com/PrefectHQ/prefect/pull/10848>

### Contributors

- @alexmojaki made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10334>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.4...2.13.5>

## Release 2.13.4

### Enhancements

- Lift API and database constraints that require task runs to have an associated flow run id — <https://github.com/PrefectHQ/prefect/pull/10816>

### Fixes

- Fix an issue with infinite scrolling on the sub flow runs tab in the UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1788>

### Documentation

- Add dark mode base job template screenshot to work pools documentation — <https://github.com/PrefectHQ/prefect/pull/10849>
- Drop beta tag from push work pools documentation — <https://github.com/PrefectHQ/prefect/pull/10799>
- Improve logo sizing and general housekeeping - <https://github.com/PrefectHQ/prefect/pull/10830>

## Release 2.13.3

## Allow configuration of a work pool's base job template via the CLI

Previously, the creation and modification of work pools, including editing the base job template, were done through the Prefect UI. Now you can alter the base job template through CLI commands:

Retrieve the default base job template for a given work pool:

```bash
prefect work-pool get-default-base-job-template --type kubernetes
```

You can customize the base job template by passing a JSON file to the `--base-job-template` flag:

```bash
prefect work-pool create my-k8s-pool --type kubernetes --base-job-template ./path/template.yaml
```

Useful for version control, you can now make updates to a work pool's base job template via the CLI:

```bash
prefect work-pool update my-work-pool --base-job-template base-job-template.json --description "My work pool" --concurrency-limit 10
```

See the documentation on [work pools](https://docs.prefect.io/latest/concepts/work-pools/) for more information, or see the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/10793>
- <https://github.com/PrefectHQ/prefect/pull/10797>
- <https://github.com/PrefectHQ/prefect/pull/10796>
- <https://github.com/PrefectHQ/prefect/pull/10798>
- <https://github.com/PrefectHQ/prefect/pull/10844>

## Allow users to customize their default flow runs view in the Prefect UI

You can now set your own default filter view on your Flow Runs page! You must first save and name a view before you can set it as your default. This setting is only stored locally so it will not be shared across machines/browsers.

<img width="1034" alt="image" src="https://github.com/PrefectHQ/prefect/assets/22418768/cd3b20e2-7df6-4336-9f6c-21f55393b745" alt="new option to set a saved filter as the default">

Note: The previous default view ("Default view") has been renamed to "Past week".

## New Google Vertex AI work pool and worker

- Run flows in containers on Google Vertex AI.
- Requires a Google Cloud Platform account and prefect-gcp library installed. Read more [here](https://prefecthq.github.io/prefect-gcp/vertex_worker/).

### Enhancements

- Display `pull_steps` on Deployments page in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/10819>
- Add `/deployments/get_scheduled_flow_runs` endpoint for retrieving scheduled flow runs from deployments — <https://github.com/PrefectHQ/prefect/pull/10817>
- Add flow run filter for fetching the first-level subflows for a given flow — <https://github.com/PrefectHQ/prefect/pull/10806>

### Fixes

- Raise `RuntimeError` error if `pip_install_requirements` step fails — <https://github.com/PrefectHQ/prefect/pull/10823>
- Use a fixed list of known collection registry views - <https://github.com/PrefectHQ/prefect/pull/10838>

### Documentation

- Fix typos in documentation and codebase — <https://github.com/PrefectHQ/prefect/pull/10813>
- Fix example in tasks concept documentation — <https://github.com/PrefectHQ/prefect/pull/10833>
- Update `git_clone` deployment step example in documentation — <https://github.com/PrefectHQ/prefect/pull/10827>
- Add `prefect deploy` guide to guide index for visibility  — <https://github.com/PrefectHQ/prefect/pull/10828>
- Fix warning in deployment storage guide documentation — <https://github.com/PrefectHQ/prefect/pull/10825>

### Contributors

- @arthurgtllr made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10833>

- @mj0nez

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.2...2.13.3>

## Release 2.13.2

### Opt-in server-side enforcement of deployment parameter schemas

We've added the ability to enforce parameter schemas for deployments via the Prefect API! This feature will prevent creation of flow runs with parameters that are incompatible with deployed flows, allowing you to discover errors sooner and avoid provisioning infrastructure for flow runs destined to fail.

Use `enforce_parameter_schema` when deploying your flow to guard against invalid parameters:

```python
from prefect import flow
from pydantic import BaseModel


class Person(BaseModel):
    name: str
    greeting: str = "Hello"


@flow(log_prints=True)
def my_flow(person: Person, name: str = "world"):
    print(f'{person.name} says, "{person.greeting}, {name}!"')


if __name__ == "__main__":
    my_flow.serve(
        "testing-params",
        enforce_parameter_schema=True,
    )

```

An attempt to run the created deployment with invalid parameters will fail and give a reason the flow run cannot be created:

```bash
> prefect deployment run 'my-flow/testing-params' -p person='{"name": 1}'

Error creating flow run: Validation failed for field 'person.name'. Failure reason: 1 is not of type 'string'
```

You can enable parameter enforcement via `prefect deploy` with the `--enforce-parameter-schema` flag or by setting `enforce_parameter_schema` to `True` in your `prefect.yaml` file.

See the following pull request for details:

- <https://github.com/PrefectHQ/prefect/pull/10773>

### Enhanced deployment flexibility with pattern-based deploying

In an effort to increase flexibility and provide more powerful deployment options, this enhancement enables users to deploy flows based on a variety of patterns, facilitating versatile and dynamic deployment management:

**Deploy all deployments for a specific flow:**

```bash
prefect deploy -n flow-a/*
```

**Deploy all deployments for a specific deployment:**

```bash
prefect deploy -n */prod
```

Note: This was previously possible in non-interactive mode with `prefect --no-prompt deploy -n prod`

**Deploy all deployments containing a specified string in the flow name:**

```bash
prefect deploy -n *extract*/*
```

**Deploy deployments with a mix of pattern matching styles**

```bash
prefect deploy -n flow-a/* -n */prod
```

**Deploy deployments with a mix of pattern matching and without:**

```bash
prefect deploy -n flow-a/* -n flow-b/default
```

See the following pull request for details:

- <https://github.com/PrefectHQ/prefect/pull/10772>

### Enhancements

- Add API route for work pool counts — <https://github.com/PrefectHQ/prefect/pull/10770>
- Add CLI command to get default base job template — <https://github.com/PrefectHQ/prefect/pull/10776>

### Fixes

- Make paths relative rather than absolute in the `prefect dev build-ui` command — <https://github.com/PrefectHQ/prefect/pull/10390>
- Lower the upper bound on pinned pendulum library — <https://github.com/PrefectHQ/prefect/pull/10752>
- Fix command handling in `run_shell_script` deployment step on Windows — <https://github.com/PrefectHQ/prefect/pull/10719>
- Fix validation on concurrency limits — <https://github.com/PrefectHQ/prefect/pull/10790>
- Fix Prefect variable resolution in deployments section of `prefect.yaml` — <https://github.com/PrefectHQ/prefect/pull/10783>

### Documentation

- Update UI screenshot for role creation — <https://github.com/PrefectHQ/prefect/pull/10732>
- Add `push work pools` tag to push work pools guide to raise visibility — <https://github.com/PrefectHQ/prefect/pull/10739>
- Update docs with recent brand changes — <https://github.com/PrefectHQ/prefect/pull/10736>
- Update Prefect Cloud quickstart guide to include new features — <https://github.com/PrefectHQ/prefect/pull/10742>
- Fix broken diagram in workers tutorial — <https://github.com/PrefectHQ/prefect/pull/10762>
- Add screenshots to artifacts concept page — <https://github.com/PrefectHQ/prefect/pull/10748>
- Remove boost from block-based deployments page in documentation and improve visibility of `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10775>
- Add example of retrieving default base job template to work pools concept documentation — <https://github.com/PrefectHQ/prefect/pull/10784>
- Add references to `enforce_parameter_schema` to docs — <https://github.com/PrefectHQ/prefect/pull/10782>
- Add documentation for pattern matching in `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10791>

### New contributors

- @danielhstahl made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10390>

- @morremeyer made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10759>
- @NikoRaisanen made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10719>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.1...2.13.2>

## Release 2.13.1

### Hide subflow runs in the Prefect UI

We’ve added the ability to filter out subflow runs from the list on the Flow Runs page! This feature is especially beneficial for those who frequently use subflows, making it easier to focus on parent flows with less clutter.

![Hide subflows in UI demo](https://github.com/PrefectHQ/prefect/assets/31014960/7f6a9473-8003-4a90-8ff7-4d766623b38b)

See the following for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/10708>

### Enhancements

- Add `run_count` to `prefect.runtime.flow_run`  — <https://github.com/PrefectHQ/prefect/pull/10676>
- Add `run_count` to `prefect.runtime.task_run`  — <https://github.com/PrefectHQ/prefect/pull/10676>
- Allow passing deployment triggers via CLI with `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10690>
- Add `is_null` filter for deployments to `/flows/filter` endpoint — <https://github.com/PrefectHQ/prefect/pull/10724>
- Show associated flow name on Custom Run page in the Prefect UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1744>
- Add ability to reset a task-based concurrency limit from the UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1746>
- Display error `details` returned by API - <https://github.com/PrefectHQ/prefect-ui-library/pull/1712>
- Add pagination to Deployments and Flows pages in the Prefect UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1732>
- Add opt-in to display large flow run graphs in Prefect UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1739>
- Add Prefect logo to UI sidebar and fix dashboard padding — <https://github.com/PrefectHQ/prefect/pull/10684>
- Add ability to update existing deployment configurations with `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10718>

### Fixes

- Avoid creating unpersisted blocks remotely — <https://github.com/PrefectHQ/prefect/pull/10649>
- Handling DST in `CronSchedules` — <https://github.com/PrefectHQ/prefect/pull/10678>
- Allow Python classes as flow/task type hints — <https://github.com/PrefectHQ/prefect/pull/10711>
- Fix formatting of `SendgridEmail.to_emails` example in notifications API reference — <https://github.com/PrefectHQ/prefect/pull/10669>
- Streamline Artifact search filters to match other pages in the Prefect UI - <https://github.com/PrefectHQ/prefect-ui-library/pull/1689>
- Improve the mobile navigation in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/10686>

### Documentation

- Add object ACL documentation — <https://github.com/PrefectHQ/prefect/pull/10695>
- Use better arrow icon for `Try Cloud` button — <https://github.com/PrefectHQ/prefect/pull/10675>
- Improves bash output format in code blocks on concepts/agents page — <https://github.com/PrefectHQ/prefect/pull/10680>
- Update concepts screen shots to reflect improved Prefect UI — <https://github.com/PrefectHQ/prefect/pull/10670>
- Update event feed screenshot in concepts pages — <https://github.com/PrefectHQ/prefect/pull/10685>
- Update Prefect Cloud index screenshots and remove Prefect Cloud quickstart — <https://github.com/PrefectHQ/prefect/pull/10692>
- Add error summaries section to Prefect Cloud index — <https://github.com/PrefectHQ/prefect/pull/10698>
- Clarify supported artifact types — <https://github.com/PrefectHQ/prefect/pull/10706>
- Update Prefect Cloud pages screenshots — <https://github.com/PrefectHQ/prefect/pull/10700>
- Fix broken links in events concept docs and variables guide — <https://github.com/PrefectHQ/prefect/pull/10726>

### New Contributors

- @odoublewen made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10706>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.13.0...2.13.1>

## Release 2.13.0

### Introducing global concurrency limits

Control task execution and system stability with Prefect's new global concurrency and rate limits.

- **Concurrency Limits:** Manage task execution efficiently, controlling how many tasks can run simultaneously. Ideal for optimizing resource usage and customizing task execution.

- **Rate Limits:** Ensure system stability by governing the frequency of requests or operations. Perfect for preventing overuse, ensuring fairness, and handling errors gracefully.

Choose concurrency limits for resource optimization and task management, and opt for rate limits to maintain system stability and fair access to services. To begin using global concurrency limits check out our [guide](https://docs.prefect.io/guides/global-concurrency-limits/).

See the following pull request for details:

- <https://github.com/PrefectHQ/prefect/pull/10496>

### Introducing work pool and worker status

Work pools and workers are critical components of Prefect's distributed execution model. To help you monitor and manage your work pools and workers, we've added status indicators to the Prefect UI.

Work pools can now have one of three statuses:

- `Ready` -  at least one online worker is polling the work pool and the work pool is ready to accept work.
- `Not Ready` - no online workers are polling the work pool and indicates that action needs to be taken to allow the work pool to accept work.
- `Paused` - the work pool is paused and work will not be executed until it is unpaused.

![Prefect dashboard showing work pool health](https://user-images.githubusercontent.com/12350579/265874237-7fae81e0-1b1a-460b-9fc5-92d969326d22.png)

Workers can now have one of two statuses:

- `Online` - the worker is polling the work pool and is ready to accept work.
- `Offline` - the worker is not polling the work pool and is not ready to accept work. Indicates that the process running the worker has stopped or crashed.

![worker table showing status](https://user-images.githubusercontent.com/12350579/265815336-c8a03c06-2b48-47c5-be93-1dbde0e5bf0d.png)

With the introduction of work pool and worker status, we are deprecating work queue health. Work queue health indicators will be removed in a future release.

See the documentation on [work pool status](https://docs.prefect.io/latest/concepts/work-pools/#work-pool-status) and [worker status](https://docs.prefect.io/latest/concepts/work-pools/#worker-status) for more information.

See the following pull request for details:

- <https://github.com/PrefectHQ/prefect/pull/10636>
- <https://github.com/PrefectHQ/prefect/pull/10654>

### Removing deprecated Orion references

Six months ago, we deprecated references to `orion` in our codebase. In this release, we're removing those references. If you still have references to `ORION` in your profile, run `prefect config validate` to automatically convert all of the settings in your _current_ profile to the new names!

For example:

```bash
❯ prefect config validate
Updated 'PREFECT_ORION_DATABASE_CONNECTION_URL' to 'PREFECT_API_DATABASE_CONNECTION_URL'.
Configuration valid!
```

#### Below is a full guide to the changes

##### Settings renamed

    - `PREFECT_LOGGING_ORION_ENABLED` → `PREFECT_LOGGING_TO_API_ENABLED`
    - `PREFECT_LOGGING_ORION_BATCH_INTERVAL` → `PREFECT_LOGGING_TO_API_BATCH_INTERVAL`
    - `PREFECT_LOGGING_ORION_BATCH_SIZE` → `PREFECT_LOGGING_TO_API_BATCH_SIZE`
    - `PREFECT_LOGGING_ORION_MAX_LOG_SIZE` → `PREFECT_LOGGING_TO_API_MAX_LOG_SIZE`
    - `PREFECT_LOGGING_ORION_WHEN_MISSING_FLOW` → `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW`
    - `PREFECT_ORION_BLOCKS_REGISTER_ON_START` → `PREFECT_API_BLOCKS_REGISTER_ON_START`
    - `PREFECT_ORION_DATABASE_CONNECTION_URL` → `PREFECT_API_DATABASE_CONNECTION_URL`
    - `PREFECT_ORION_DATABASE_MIGRATE_ON_START` → `PREFECT_API_DATABASE_MIGRATE_ON_START`
    - `PREFECT_ORION_DATABASE_TIMEOUT` → `PREFECT_API_DATABASE_TIMEOUT`
    - `PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT` → `PREFECT_API_DATABASE_CONNECTION_TIMEOUT`
    - `PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS` → `PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME`
    - `PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`
    - `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS`
    - `PREFECT_ORION_API_DEFAULT_LIMIT` → `PREFECT_API_DEFAULT_LIMIT`
    - `PREFECT_ORION_API_HOST` → `PREFECT_SERVER_API_HOST`
    - `PREFECT_ORION_API_PORT` → `PREFECT_SERVER_API_PORT`
    - `PREFECT_ORION_API_KEEPALIVE_TIMEOUT` → `PREFECT_SERVER_API_KEEPALIVE_TIMEOUT`
    - `PREFECT_ORION_UI_ENABLED` → `PREFECT_UI_ENABLED`
    - `PREFECT_ORION_UI_API_URL` → `PREFECT_UI_API_URL`
    - `PREFECT_ORION_ANALYTICS_ENABLED` → `PREFECT_SERVER_ANALYTICS_ENABLED`
    - `PREFECT_ORION_SERVICES_SCHEDULER_ENABLED` → `PREFECT_API_SERVICES_SCHEDULER_ENABLED`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED` → `PREFECT_API_SERVICES_LATE_RUNS_ENABLED`
    - `PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED` → `PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED`
    - `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_ENABLED` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED`
    - `PREFECT_ORION_TASK_CACHE_KEY_MAX_LENGTH` → `PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH`
    - `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_ENABLED` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED`

##### Changes

    - Module `prefect.client.orion` → `prefect.client.orchestration`
    - Command group `prefect orion` → `prefect server`
    - Module `prefect.orion` → `prefect.server`
    - Logger `prefect.orion` → `prefect.server`
    - Constant `ORION_API_VERSION` → `SERVER_API_VERSION`
    - Kubernetes deployment template application name changed from `prefect-orion` → `prefect-server`
    - Command `prefect kubernetes manifest orion` → `prefect kubernetes manifest server`
    - Log config handler `orion` → `api`
    - Class `OrionLogWorker` → `APILogWorker`
    - Class `OrionHandler` → `APILogHandler`
    - Directory `orion-ui` → `ui`
    - Class `OrionRouter` → `PrefectRouter`
    - Class `OrionAPIRoute` → `PrefectAPIRoute`
    - Class `OrionDBInterface` → `PrefectDBInterface`
    - Class `OrionClient` → `PrefectClient`

See the following pull request for details:

- Remove deprecated `orion` references — <https://github.com/PrefectHQ/prefect/pull/10642>

### Fixes

- Fix an issue with `prefect server start` on Windows - <https://github.com/PrefectHQ/prefect/pull/10547>

### Documentation

- Update deployment concept documentation to emphasize server-side deployment — <https://github.com/PrefectHQ/prefect/pull/10615>
- Add Kubernetes guide for deploying worker to Azure AKS — <https://github.com/PrefectHQ/prefect/pull/10575>
- Add information on `--no-prompt` and `PREFECT_CLI_PROMPT` to deployment documentation — <https://github.com/PrefectHQ/prefect/pull/10600>
- Fix broken link to docker guide with redirect and harmonize naming — <https://github.com/PrefectHQ/prefect/pull/10624>
- Remove invalid link in API keys documentation — <https://github.com/PrefectHQ/prefect/pull/10658>
- Update screenshots and CLI log output in quickstart documentation — <https://github.com/PrefectHQ/prefect/pull/10659>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.12.1...2.13.0>

## Release 2.12.1

This release includes some important fixes and enhancements. In particular, it resolves an issue preventing the flow run graph from rendering correctly in some cases.

### Enhancements

- Reduce logging noise on QueueServices startup failures and item processing failures — <https://github.com/PrefectHQ/prefect/pull/10564>
- Expose a setting for configuring a process limit on served flows — <https://github.com/PrefectHQ/prefect/pull/10602>

### Fixes

- Improve failure recovery for websockets — <https://github.com/PrefectHQ/prefect/pull/10597>
- Fix flow run graph rendering issues — <https://github.com/PrefectHQ/prefect/pull/10606>

### Documentation

- Update Docker guide to include with `flow.serve()` — <https://github.com/PrefectHQ/prefect/pull/10596>

### Contributors

- @urimandujano made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10564>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.12.0...2.12.1>

## Release 2.12.0

### Introducing `Flow.serve()`

We're excited to introduce a radically simple way to deploy flows.

The new `.serve()` method available on every flow allows you to take your existing flows and schedule or trigger runs via the Prefect UI and CLI.

This addition makes it easier than it's ever been to deploy flows with Prefect:

```python title="hello.py"
from prefect import flow

@flow
def hello(name = "Marvin"):
    print(f"Hello {name}!")

if __name__ == "__main__":
    # Creates a deployment named 'hello/hourly-greeting'
    # which will run the 'hello' flow once an hour
    hello.serve(name="hourly-greeting", interval=3600)
```

Running this script will start a process that will run the `hello` flow every hour and make it triggerable via the Prefect UI or CLI:

```
> python hello.py
╭─────────────────────────────────────────────────────────────────────────────────────╮
│ Your flow 'hello' is being served and polling for scheduled runs!                   │
│                                                                                     │
│ To trigger a run for this flow, use the following command:                          │
│                                                                                     │
│         $ prefect deployment run 'hello/hourly-greeting'                            │
│                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────╯
```

To start serving your flows, check out our newly updated [quickstart](https://docs.prefect.io/latest/getting-started/quickstart/) and [tutorial](https://docs.prefect.io/latest/tutorial/).

See the following pull requests for details:

- <https://github.com/PrefectHQ/prefect/pull/10534>
- <https://github.com/PrefectHQ/prefect/pull/10549>
- <https://github.com/PrefectHQ/prefect/pull/10574>
- <https://github.com/PrefectHQ/prefect/pull/10585>

### A fresh look and feel

The Prefect UI just got a fresh coat of paint! We've carefully updated colors throughout the UI to ensure a more cohesive and visually appealing experience. Whether you're a fan of the light or dark side (or switch between both), you'll notice our interfaces now shine brighter and feel more harmonious. Dive in and explore the new hues!

![Updated Prefect UI in light and dark modes](https://github.com/PrefectHQ/prefect/assets/42048900/c526619c-22d3-44e6-82ee-255ae1233035)

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/10546>
- <https://github.com/PrefectHQ/prefect/pull/10578>
- <https://github.com/PrefectHQ/prefect/pull/10584>
- <https://github.com/PrefectHQ/prefect/pull/10583>
- <https://github.com/PrefectHQ/prefect/pull/10588>

### Enhancements

- Allow JSON infra overrides via `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10355>
- Improve validation for `Flow.name` — <https://github.com/PrefectHQ/prefect/pull/10463>
- Add a Docker image for conda for Python 3.11 — <https://github.com/PrefectHQ/prefect/pull/10532>
- Increase default `PREFECT_API_REQUEST_TIMEOUT` setting to 60 seconds — <https://github.com/PrefectHQ/prefect/pull/10543>
- Remove missing work queue warning from the deployment page — <https://github.com/PrefectHQ/prefect/pull/10550>
- Add `PREFECT_SQLALCHEMY_POOL_SIZE` and `PREFECT_SQLALCHEMY_MAX_OVERFLOW` settings to configure SQLAlchemy connection pool size — <https://github.com/PrefectHQ/prefect/pull/10348>
- Improve format handling of `GitLab` and `Bitbucket` tokens during `git_clone` deployment step — <https://github.com/PrefectHQ/prefect/pull/10555>
- Persist active tabs in Prefect UI pages upon refresh — <https://github.com/PrefectHQ/prefect/pull/10544>
- Add ability to view subflows in the UI that are linked from `run_deployment` with `DaskTaskRunner` and `RayTaskRunner` — <https://github.com/PrefectHQ/prefect/pull/10541>
- Improve CLI output for push work pools <https://github.com/PrefectHQ/prefect/pull/10582>

### Fixes

- Pin `anyio` to < 4 in `requirements.txt` — <https://github.com/PrefectHQ/prefect/pull/10570>
- Add upper bounds to core requirements to prevent major version upgrades <https://github.com/PrefectHQ/prefect/pull/10592>
- Fix race condition in concurrent subflow runs involving `AsyncWaiters` — <https://github.com/PrefectHQ/prefect/pull/10533>
- Fix `cloud login` false success when `PREFECT_API_KEY` set as environment variable or expired — <https://github.com/PrefectHQ/prefect/pull/8641>
- Fix ability to view deployments page tags on larger screens - <https://github.com/PrefectHQ/prefect/pull/10566>
- Properly indent `docker-git` recipe `prefect.yaml` — <https://github.com/PrefectHQ/prefect/pull/10519>
- Fix Slack community invitation link — <https://github.com/PrefectHQ/prefect/pull/10509>

### Experimental

- Serialize concurrency requests — <https://github.com/PrefectHQ/prefect/pull/10545>

### Documentation

- Detail Kubernetes work pool usage in Kubernetes guide — <https://github.com/PrefectHQ/prefect/pull/10516>
- Add quickstart documentation, simplify welcome page and API reference overview — <https://github.com/PrefectHQ/prefect/pull/10520>
- Add block and agent-based deployments to leftside navigation — <https://github.com/PrefectHQ/prefect/pull/10528>
- Add `Try Prefect Cloud` button to documentation header — <https://github.com/PrefectHQ/prefect/pull/10537>
- Remove blank menu bar in documentation header — <https://github.com/PrefectHQ/prefect/pull/10565>
- Fix link to guide on moving data to and from cloud providers — <https://github.com/PrefectHQ/prefect/pull/10521>
- Shorten push work pools description in guides index — <https://github.com/PrefectHQ/prefect/pull/10589>
- Organize guides index into sections: Development, Execution, Workers and Agents, and Other Guides — <https://github.com/PrefectHQ/prefect/pull/10587>

### Contributors

- @mattklein

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.5...2.12.0>

## Release 2.11.5

### New Guides

We're happy to announce two new guides to help you get the most out of Prefect!

#### How to move data to and from cloud providers

Moving data to cloud-based storage and retrieving it is crucial in many data engineering setups. [This guide](https://docs.prefect.io/latest/guides/moving-data/) provides step-by-step instructions to seamlessly integrate and interact with popular cloud services like AWS, Azure, and GCP.

#### Running flows with Kubernetes

For those aiming to optimize their flows using Kubernetes, this guide provides a deep dive on how to efficiently run flows on Kubernetes using containers. Catering to both novices and seasoned experts, [this guide](https://docs.prefect.io/latest/guides/deployment/kubernetes/) offers insights for all proficiency levels.

See the following pull requests for details:

- <https://github.com/PrefectHQ/prefect/pull/10133>
- <https://github.com/PrefectHQ/prefect/pull/10368>
- <https://github.com/PrefectHQ/prefect/pull/10591>

### Enhancements

- Warn users upon setting a misconfigured `PREFECT_API_URL` — <https://github.com/PrefectHQ/prefect/pull/10450>
- Show CLI warning if worker is polling a paused work pool or queue  — <https://github.com/PrefectHQ/prefect/pull/10369>
- Optimize the query generated by the `/task_runs` endpoint — <https://github.com/PrefectHQ/prefect/pull/10422>
- Extend optimization on `/task_runs` endpoint to include safety guard — <https://github.com/PrefectHQ/prefect/pull/10466>
- Add `DiscordWebhook` notification block — <https://github.com/PrefectHQ/prefect/pull/10394>
- Remove reference to deprecated `prefect project ls` in interactive `prefect deploy` command — <https://github.com/PrefectHQ/prefect/pull/10473>

### Fixes

- Remove base job template validation when work pools are read — <https://github.com/PrefectHQ/prefect/pull/10486>

### Experimental

- Codify concurrency context managers and rate limiting with tests — <https://github.com/PrefectHQ/prefect/pull/10414>

### Documentation

- Add reference to workers in flows documentation admonition — <https://github.com/PrefectHQ/prefect/pull/10464>
- Combine Kubernetes worker and flows pages — <https://github.com/PrefectHQ/prefect/pull/10448>
- Remove references to `flow_name` from deployments documentation — <https://github.com/PrefectHQ/prefect/pull/10477>
- Improve readability of Kubernetes guide  — <https://github.com/PrefectHQ/prefect/pull/10481>
- Fix typos in contribution and host documentation — <https://github.com/PrefectHQ/prefect/pull/10488>
- Raise visibility of push work pools documentation — <https://github.com/PrefectHQ/prefect/pull/10497>
- Fix heading size, remove unnecessary link in deployments documentation — <https://github.com/PrefectHQ/prefect/pull/10489>
- Add GCP-specific guide for deploying a GKE cluster to host a worker — <https://github.com/PrefectHQ/prefect/pull/10490>
- Fix typo in `prefect-gcs` deployment example — <https://github.com/PrefectHQ/prefect/pull/10442>
- Move guide on upgrading from agents to workers — <https://github.com/PrefectHQ/prefect/pull/10445>
- Fix grammatical errors in documentation — <https://github.com/PrefectHQ/prefect/pull/10457>
- Clarify deployments variables and fix `prefect.yaml` example — <https://github.com/PrefectHQ/prefect/pull/10474>
- Update `README` header image with new Prefect branding — <https://github.com/PrefectHQ/prefect/pull/10493>

## Contributors

- @mattklein made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10422>
- @vishalsanfran made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10394>
- @AmanSal1
- @mj0nez

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.4...2.11.5>

## Release 2.11.4

### Guide to upgrade from agents to workers

Upgrading to workers significantly enhances the experience of deploying flows. It simplifies the specification of each flow's infrastructure and runtime environment.

A [worker](/concepts/work-pools/#worker-overview) is the fusion of an [agent](/concepts/agents/) with an [infrastructure block](/concepts/infrastructure/). Like agents, workers poll a work pool for flow runs that are scheduled to start. Like infrastructure blocks, workers are typed - they work with only one kind of infrastructure and they specify the default configuration for jobs submitted to that infrastructure.

We've written [a handy guide](https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/) that describes how to upgrade from agents to workers in just a few quick steps.

### Visualize your flow before running it

Until now, the only way to produce a visual schematic of a flow has been to run it and view the corresponding flow run page in the Prefect UI. Some flows, though, are time consuming or expensive to run. Now, you can get a quick sense of the structure of your flow using the `.visualize()` method. Calling this method will attempt to locally produce an image of the flow's schematic diagram without running the flow's code.

![viz-return-value-tracked](https://github.com/PrefectHQ/prefect/assets/3407835/325ef46e-82ce-4400-93d2-b3110c805116)

See the [flows documentation](https://docs.prefect.io/latest/concepts/flows/#visualizing-flow-structure) or the [pull request](https://github.com/PrefectHQ/prefect/pull/10417) for more information.

### Enhancements

- Update `prefect deploy` to skip building docker image prompt if `build` key explicitly set to null in `prefect.yaml` — <https://github.com/PrefectHQ/prefect/pull/10371>
- Handle spot instance eviction in Kubernetes Infrastructure Block — <https://github.com/PrefectHQ/prefect/pull/10426>

### Fixes

- Reduce wait time between tasks by adding a clause to the visiting function to raise if it encounters a quote annotation — <https://github.com/PrefectHQ/prefect/pull/10370>
- Enable dashboard filters to update with each polling interval so the 24h time span constantly updates — <https://github.com/PrefectHQ/prefect/pull/10327>
- Resolve issue with validation of templated variables in base job template of work pool — <https://github.com/PrefectHQ/prefect/pull/10385>
- Update CLI to refer to a "work pool" instead of a "worker pool" — <https://github.com/PrefectHQ/prefect/pull/10309>

### Documentation

- Elevate Guides in navigation and remove migration guide — <https://github.com/PrefectHQ/prefect/pull/10361>
- Update notes about community support — <https://github.com/PrefectHQ/prefect/pull/10322>
- Update concepts page to clean up table and remove unnecessary header — <https://github.com/PrefectHQ/prefect/pull/10374>
- Improve headings on deployments concept page — <https://github.com/PrefectHQ/prefect/pull/10366>
- Update the storage guide for Bitbucket to add `x-token-auth` — <https://github.com/PrefectHQ/prefect/pull/10379>
- Add Planetary Computer collection — <https://github.com/PrefectHQ/prefect/pull/10387>
- Highlight `@flow` decorator instead of function in tutorial — <https://github.com/PrefectHQ/prefect/pull/10401>
- Update tutorial summary list — <https://github.com/PrefectHQ/prefect/pull/10403>
- Update Cloud connection guide to include whitelisting URLs — <https://github.com/PrefectHQ/prefect/pull/10418>
- Update code snippets and highlighting in tutorial — <https://github.com/PrefectHQ/prefect/pull/10391>
- Remove "Reference Material" section from tutorial — <https://github.com/PrefectHQ/prefect/pull/10402>
- Fix typo in schedules concept page — <https://github.com/PrefectHQ/prefect/pull/10378>
- Fix typo on artifacts concept page — <https://github.com/PrefectHQ/prefect/pull/10380>

### Contributors

- @shahrukhx01 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10378>
- @giorgiobasile
- @marwan116

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.3...2.11.4>

## Release 2.11.3

## Enhanced support for environment variables in `run_shell_script` step

Previously, to expand environment variables in the `run_shell_script` step, you had to enclose your scripts in `bash -c`. We have optimized this process by introducing a new field: `expand_env_vars`. By setting this field to `true`, you can easily pass environment variables to your script.

Consider the following example where the script utilizes the `$USER` environment variable:

```yaml
pull:
    - prefect.deployments.steps.run_shell_script:
        script: |
            echo "User: $USER"
            echo "Home Directory: $HOME"
        stream_output: true
        expand_env_vars: true
```

For implementation details, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10198>

### Enhancements

- Change language for `--ci` option in `prefect deploy --help`. — <https://github.com/PrefectHQ/prefect/pull/10347>

### Experimental

- Port concurrency limit v2 API and modeling from Prefect Cloud — <https://github.com/PrefectHQ/prefect/pull/10363>

### Documentation

- Add Prefect Cloud quickstart to navigation menu — <https://github.com/PrefectHQ/prefect/pull/10350>
- Fix typo in deployments documentation — <https://github.com/PrefectHQ/prefect/pull/10353>
- Reorganize concepts pages — <https://github.com/PrefectHQ/prefect/pull/10359>

### Contributors

- @AmanSal1

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.2...2.11.3>

## Release 2.11.2

### Enhancements

- Explicitly set all calls to `pendulum.now()` to "UTC" — <https://github.com/PrefectHQ/prefect/pull/10320>

### Documentation

- Add guide for specifying storage for deployments — <https://github.com/PrefectHQ/prefect/pull/10150>
- Add ACI push work pool guide — <https://github.com/PrefectHQ/prefect/pull/10323>
- Move some concepts and cloud pages to guides section — <https://github.com/PrefectHQ/prefect/pull/10328>

### Deprecations

- Deprecate `FlowRunCreate.deployment_id` — <https://github.com/PrefectHQ/prefect/pull/10324>

### Contributors

- @psofiterol made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10320>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.1...2.11.2>

## Release 2.11.1

### Enhancements

- Add `work_queue_name` field when creating a flow run for a deployment, enabling the queue setting to be overridden on a per-run basis — <https://github.com/PrefectHQ/prefect/pull/10276>
- Prevent accidental credential logging on BindFailure by logging only a list of key names, but not the values — <https://github.com/PrefectHQ/prefect/pull/10264>
- Allow task runs to explicitly return `Paused` states, therefore pausing the flow run using the same settings — <https://github.com/PrefectHQ/prefect/pull/10269>

### Fixes

- Hide links to work queues for push work pools — <https://github.com/PrefectHQ/prefect-ui-library/pull/1603>
- Fix issue with `Pause` state fields — <https://github.com/PrefectHQ/prefect-ui-library/pull/1606>
- Fix issue with flow run logs missing until after refresh — <https://github.com/PrefectHQ/prefect-ui-library/pull/1594>

### Experimental

- Add a general use concurrency context manager — <https://github.com/PrefectHQ/prefect/pull/10267>
- Add `rate_limit` function to block execution while acquiring slots — <https://github.com/PrefectHQ/prefect/pull/10299>

### Documentation

- Add redirect to quickstart page — <https://github.com/PrefectHQ/prefect/pull/10292>
- Add missing quotation mark in docstring — <https://github.com/PrefectHQ/prefect/pull/10286>
- Fix `run_deployment` docstring rendering — <https://github.com/PrefectHQ/prefect/pull/10310>
- Fix type in deployment docs — <https://github.com/PrefectHQ/prefect/pull/10303>

### Contributors

- @Sche7 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10286>
- @LennyArdiles made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10264>
- @Akshat0410 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10303>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.11.0...2.11.1>

## Release 2.11.0

### Flow summary graphs and stats

Each flow page now includes graphs of its recent flow runs, task runs, and (in Prefect Cloud) related events, as well as summary statistics!

<img width="1373" alt="Screenshot 2023-07-20 at 3 42 51 PM" src="https://github.com/PrefectHQ/prefect/assets/3407835/5a914db7-7373-4396-8515-272201bbbfa1">

Flow details have been moved to a dedicated tab. For implementation details, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10242>

### Work pools and workers are now generally available

Since first being introduced in Prefect 2.10.0, Prefect [workers and work pools](https://docs.prefect.io/2.10.21/concepts/work-pools/) have come a long way. There are now work pools for every major infrastructure type. Work pools expose rich configuration of their infrastructure. Every work pool type has a base configuration with sensible defaults such that you can begin executing work with just a single command. The infrastructure configuration is fully customizable from the Prefect UI.

Push work pools, recently released in Prefect Cloud, remain a beta feature.

For implementation details, see the following pull requests:

- <https://github.com/PrefectHQ/prefect/pull/10244>
- <https://github.com/PrefectHQ/prefect/pull/10243>

### Enhancements

- Use `orjson_dumps_extra_compatible` when serializing in `build_from_flow`  — <https://github.com/PrefectHQ/prefect/pull/10232>

### Fixes

- Make `resolve_futures_to_data` function raise on failure by default — <https://github.com/PrefectHQ/prefect/pull/10197>
- Fix flow runs page not polling for new runs and not loading more flow runs when scrolling — <https://github.com/PrefectHQ/prefect/pull/10247>
- Don't create DB default during settings load — <https://github.com/PrefectHQ/prefect/pull/10246>
- Fix issues causing flow runs to be incorrectly marked as failed — <https://github.com/PrefectHQ/prefect/pull/10249>
- Fix incorrect path in error message — <https://github.com/PrefectHQ/prefect/pull/10255>
- Fix `LocalFileSystem.get_directory` with basepath behaviour  — <https://github.com/PrefectHQ/prefect/pull/10258>
- Fix Dashboard refresh cadence — <https://github.com/PrefectHQ/prefect/pull/10227>

### Documentation

- Add undocumented runtime parameters — <https://github.com/PrefectHQ/prefect/pull/10229>
- Add Deployment Quickstart — <https://github.com/PrefectHQ/prefect/pull/9985>
- Add guide for setting up a push work pool — <https://github.com/PrefectHQ/prefect/pull/10248>
- Add guide for deploying a flow using Docker — <https://github.com/PrefectHQ/prefect/pull/10252>
- Edit install and quickstart pages for clarity — <https://github.com/PrefectHQ/prefect/pull/10231>
- Update automations screenshots — <https://github.com/PrefectHQ/prefect/pull/10245>
- Fix typos on Deployment Management page — <https://github.com/PrefectHQ/prefect/pull/10241>
- Fix flow retries example — <https://github.com/PrefectHQ/prefect/pull/10233>
- Fix missing document title and adding terminal login section — <https://github.com/PrefectHQ/prefect/pull/10256>

### Contributors

- @dbentall made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10258>
- @mesejo

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.21...2.11.0>

## Release 2.10.21

### The Prefect Dashboard - your heads up display

The response to the experimental Prefect dashboard was so enthusiastic that we've made it generally available as the default landing page in the Prefect UI. The dashboard provides an overview of all Prefect activity, surfaces the urgent information, and provides the context to understand that information. With the dashboard, you can:

- Confirm that all flows run in the past 24 hours behaved as expected
- Identify a flow run that recently failed and jump directly to its page
- See a work pool that is unhealthy and the work that is impacted

### Deploy deployments prefixed by flow name during `prefect deploy`

You can now specify the deployment to be executed by prefixing the deployment name with the flow name.

For example, the following command creates a deployment with the name `my-deployment` for a flow with the name `my-flow`:

```bash
prefect deploy --name my-flow/my-deployment
```

This is especially useful when you have several flows with deployments that have the same name.

For implementation details, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10189>

### Use environment variables in deployment steps

Prefect now supports the usage of environment variables in deployment steps, allowing you to access environment variables during the `pull` action at runtime or during the `build` and `push` actions when running `prefect deploy`. Particularly useful for CI/CD builds, this makes Prefect deployments more versatile.

For example, you can now use the following syntax to set an image tag of a Dockerized build by loading an environment variable during the `build` action:

```yaml
build:
- prefect_docker.deployments.steps.build_docker_image:
    requires: prefect-docker>0.1.0
    image_name: my-image/orion
    tag: '{{ $CUSTOM_TAG }}'
```

You can also use environment variables inside of steps.

For example:

```yaml
- prefect.deployments.steps.run_shell_script:
    script: echo "test-'{{ $PREFECT_API_URL }}'"
    stream_output: true
```

For implementation details, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10199>

### Use `prefect deploy` with multiple deployments with the same name

When there are multiple deployments with the same name, the `prefect deploy` command now prompts you to choose which one to deploy:

For example, if you have the following `prefect.yaml`:

```yaml
deployments:
- name: "default"
  entrypoint: "flows/hello.py:hello"

- name: "default"
  entrypoint: "flows/hello.py:hello_parallel"
```

running `prefect deploy -n default` will now prompt you to choose which flow to create a deployment for:

<img width="904" alt="prompt choose a deployment" src="https://github.com/PrefectHQ/prefect/assets/42048900/bff5369f-9568-41c9-a2b1-b2ecdd6cd8c8">

For implementation details, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10189>

### Enhancements

- Enable workspace dashboard by default — <https://github.com/PrefectHQ/prefect/pull/10202>
- Add `SendgridEmail` notification block — <https://github.com/PrefectHQ/prefect/pull/10118>
- Raise state change hook errors during creation if not correctly formatted — <https://github.com/PrefectHQ/prefect/pull/9692>
- Improve `prefect deploy` nonexistent entrypoint `ValueError` - <https://github.com/PrefectHQ/prefect/pull/10210>
- Truncate row length in interactive `prefect deploy` table display - <https://github.com/PrefectHQ/prefect/pull/10209>
- Add `prefect.runtime.flow_run.parent_flow_run_id` and `prefect.runtime.flow_run.parent_deployment_id` - <https://github.com/PrefectHQ/prefect/pull/10204>

### Fixes

- Adds handling for failed Kubernetes jobs — <https://github.com/PrefectHQ/prefect/pull/10125>

### Documentation

- Fix formatting in `mkdocs.yml` — <https://github.com/PrefectHQ/prefect/pull/10187>
- Fix link to API docs in automations documentation — <https://github.com/PrefectHQ/prefect/pull/10208>
- Remove the duplicate listing in installation documentation — <https://github.com/PrefectHQ/prefect/pull/10200>
- Fix example in proactive trigger documentation — <https://github.com/PrefectHQ/prefect/pull/10203>
- Remove references to nonexistent `prefect profile get` - <https://github.com/PrefectHQ/prefect/pull/10214>

## Contributors

- @rkscodes

- @Ishankoradia made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10118>
- @bsenst made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10200>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.20...2.10.21>

## Release 2.10.20

### Resolving UI form input issues

This release resolves bugs preventing UI form inputs from being rendered and parsed correctly, including:

- Dates & times — <https://github.com/PrefectHQ/prefect-ui-library/pull/1554>
- List values — <https://github.com/PrefectHQ/prefect-ui-library/pull/1556>
- JSON fields — <https://github.com/PrefectHQ/prefect-ui-library/pull/1557>

### Prefect no longer supports Python 3.7

Python 3.7 reached end-of-life on 27 Jun 2023. Consistent with our warning, this release drops Python 3.7 support. Prefect now requires Python 3.8 or later.

### Enhancements

- Add UUID validation for webhook CLI commands to raise errors earlier and more clearly — <https://github.com/PrefectHQ/prefect/pull/10005>
- Clarify Dockerfile rename prompt in `prefect deploy` — <https://github.com/PrefectHQ/prefect/pull/10124>
- Improve `prefect deploy` error message — <https://github.com/PrefectHQ/prefect/pull/10175>
- Add `work_pool_name` to `Deployment` docstring — <https://github.com/PrefectHQ/prefect/pull/10174>

### Contributors

- @toby-coleman

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.19...2.10.20>

## Release 2.10.19

### Peer into the future with the experimental dashboard

We're excited to make the new Prefect dashboard available as an experimental feature. The dashboard provides an overview of all Prefect activity, surfaces the urgent information, and provides the context to understand that information. With the dashboard, you can:

- Confirm that all flows run in the past 24 hours behaved as expected
- Identify a flow run that recently failed and jump directly to its page
- See a work pool that is unhealthy and the work that is impacted

You can enable the new dashboard by running `prefect config set PREFECT_EXPERIMENTAL_ENABLE_WORKSPACE_DASHBOARD=True` in your terminal.

See [this pull request](https://github.com/PrefectHQ/prefect/pull/10152) for implementation details.

### Improvements to `git_clone` deployment pull step

Previously, users had to apply the appropriate format for their service credentials in a `Secret` block using the `access_token` field in `git_clone`. The `git_clone` pull step now includes an additional `credentials` field, allowing users to leverage their existing `GitHubCredentials`, `GitLabCredentials`, or `BitBucketCredentials` blocks when cloning from a private repository. For examples of providing credentials, see the [updated documentation](https://docs.prefect.io/2.10.19/concepts/deployments-ux/#the-pull-action).

For implementation details see:

- <https://github.com/PrefectHQ/prefect/pull/10157>

### Fixes

- Improve language in `prefect deploy` to not recommend deprecated `-f/--flow` — <https://github.com/PrefectHQ/prefect/pull/10121>
- Pin Pydantic to v1 in `requirements.txt` — <https://github.com/PrefectHQ/prefect/pull/10144>
- Add default value of `None` for `WorkQueue.work_pool_id` — <https://github.com/PrefectHQ/prefect/pull/10106>

### Documentation

- Update `git_clone` documentation with examples of using credentials field - <https://github.com/PrefectHQ/prefect/pull/10168>
- Add documentation on deleting blocks — <https://github.com/PrefectHQ/prefect/pull/10115>
- Add docs tabs linking and styling  — <https://github.com/PrefectHQ/prefect/pull/10113>
- Fix example in `Block.load` docstring — <https://github.com/PrefectHQ/prefect/pull/10098>
- Fix task tutorial documentation example — <https://github.com/PrefectHQ/prefect/pull/10120>
- Clarify heading in rate limits documentation — <https://github.com/PrefectHQ/prefect/pull/10148>
- Fix link in events documentation — <https://github.com/PrefectHQ/prefect/pull/10160>
- Remove outdated disclaimer about configuring webhooks with the Prefect Cloud UI — <https://github.com/PrefectHQ/prefect/pull/10167>

### Integrations

- Add `prefect-earthdata` integration — <https://github.com/PrefectHQ/prefect/pull/10151>

### Contributors

- @rkscodes
- @StefanBRas

- @JordonMaule made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10120>

- @AmanSal1 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10121>
- @giorgiobasile made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10151>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.18...2.10.19>

## Release 2.10.18

### Docker image support during flow deployment

We enhanced support for Docker-based infrastructures when deploying flows through the interactive `prefect deploy` experience. Users can now easily custom-build or auto-build Docker images and push them to remote registries if they so choose.

The CLI automatically detects if a work pool supports Docker images (e.g., docker, ecs, cloud-run) during `prefect deploy` and will now guide the user through the experience of building and pushing a Docker image if support is detected.

This enhancement to managing deployments will greatly simplify the process of creating `build` and `push` steps for deployments.

Not only that, we will also create a `pull` step for you when you choose to build a Docker image through `prefect deploy`. Whether you have your own Dockerfile or you want to use the auto-build feature in `build_docker_image`, we will create a `pull` step for you to help you set the correct path to your flow code.

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/10022>
- <https://github.com/PrefectHQ/prefect/pull/10090>

### Event-driven deployments with triggers

You can now easily incorporate event-based triggers into your Prefect Cloud deployments - simply add triggers to your `prefect.yaml` file or directly from the Prefect UI deployment page. Deployment triggers utilize automations - any automation that runs flows from a given deployment will be reflected on that deployment page.

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/10049>
- <https://github.com/PrefectHQ/prefect/pull/10097>

### Enhancements

- Allow saving of updated deployment configurations — <https://github.com/PrefectHQ/prefect/pull/10018>
- Add `--install-policy` option to `prefect worker start` - <https://github.com/PrefectHQ/prefect/pull/10040>
- Update Docker-based `prefect init` recipes to use `push_docker_image` step — <https://github.com/PrefectHQ/prefect/pull/10092>

### Fixes

- Fix deployment `pull` step saving by preserving placeholders with missing values — <https://github.com/PrefectHQ/prefect/pull/10053>
- Fix `prefect server start` and `prefect agent start` on Windows — <https://github.com/PrefectHQ/prefect/pull/10059>
- Add ability to use Prefect variables in `job_variables` section of deploy config in `prefect.yaml` — <https://github.com/PrefectHQ/prefect/pull/10078>
- Add default option to `new_parameters.pop` in `explode_variadic_parameter` used to handle `**kwargs` in task mapping — <https://github.com/PrefectHQ/prefect/pull/10067>
- Skip schedule prompts in `prefect deploy` if schedule is set or null in `prefect.yaml` — <https://github.com/PrefectHQ/prefect/pull/10074>
- Fix saving of `pull` and `push` step deployment configuration — <https://github.com/PrefectHQ/prefect/pull/10087>
- Fix issue hosting and running the UI in unsecured contexts - <https://github.com/PrefectHQ/prefect-design/pull/829>

### Documentation

- Adjust docs to reflect Prefect requires Python 3.8 — <https://github.com/PrefectHQ/prefect/pull/9853>
- Add custom `pull` step examples to deployment management docs — <https://github.com/PrefectHQ/prefect/pull/10073>
- Add troubleshooting guide to docs — <https://github.com/PrefectHQ/prefect/pull/10079>
- Add information on finding Prefect Cloud account id and workspace id — <https://github.com/PrefectHQ/prefect/pull/10103>
- Reference webhooks documentation from events documentation — <https://github.com/PrefectHQ/prefect/pull/10045>
- Simplify deployment description in docs — <https://github.com/PrefectHQ/prefect/pull/10050>

### Contributors

- @garylavayou made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10060>
- @themattmorris made their first contribution in <https://github.com/PrefectHQ/prefect/pull/10056>
- @NodeJSmith
- @rpeden

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.17...2.10.18>

## Release 2.10.17

### Improved Prefect tutorial

Prefect's documentation has an [improved tutorial](https://docs.prefect.io/2.10.17/tutorial/), redesigned to include Prefect's recent enhancements. With the introduction of work pools and the interactive deployment CLI, the new tutorial reflects the elevated experience that these new features offer, alongside the key elements and features of Prefect. You can find content related to more advanced features or less common use cases in the [Guides](https://docs.prefect.io/2.10.17/guides/) section.

### Enhancements

- Update Prefect client to follow redirects by default — <https://github.com/PrefectHQ/prefect/pull/9988>
- Always show checkboxes on list items, rather than animating them on hover — <https://github.com/PrefectHQ/prefect-ui-library/pull/1490>
- New `CustomWebhookNotificationBlock` for triggering custom webhooks in response to flow run state changes — <https://github.com/PrefectHQ/prefect/pull/9547>

### Fixes

- Limit the number of files concurrently opened by `prefect deploy` when searching for flows — <https://github.com/PrefectHQ/prefect/pull/10014>
- Fix `TypeError: crypto.randomUUID is not a function` that caused pages to break — <https://github.com/PrefectHQ/prefect-ui-library/pull/1501>

### Documentation

- Fix broken link to `prefect-docker` documentation on the deployments UX page — <https://github.com/PrefectHQ/prefect/pull/10013>
- Document `--work-queue / -q` arguments to `worker start` command — <https://github.com/PrefectHQ/prefect/pull/10027>
- Add link to join Club 42 to Community page — <https://github.com/PrefectHQ/prefect/pull/9927>
- Improve Prefect tutorial to be more succinct and purposeful  — <https://github.com/PrefectHQ/prefect/pull/9940>

### Contributors

- @eclark9270 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9927>

- @AutumnSun1996 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9547>
- @dianaclarke made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9988>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.16...2.10.17>

## Release 2.10.16

### Run `prefect deploy` without providing a flow entrypoint

We're making it easier than ever to deploy your first flow! Previously, you needed to run `prefect deploy <entrypoint>` to deploy a specific flow. Now, you can simply run `prefect deploy` and the interactive CLI will guide you through the process of selecting a flow to deploy!

![flow selector example](https://user-images.githubusercontent.com/12350579/247144440-d89916d4-cbf1-408e-9959-45df94a35f8d.png)

For more details on implementation, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/10004>

### Enhancements

- Add option to specify work queue priority during creation from CLI — <https://github.com/PrefectHQ/prefect/pull/9999>
- Improve 'Invalid timezone' error message — <https://github.com/PrefectHQ/prefect/pull/10007>

### Fixes

- Fix wrong key used in generated `git_clone` step — <https://github.com/PrefectHQ/prefect/pull/9997>

### Deprecations

- Deprecate `prefect deploy` `--ci` flag — <https://github.com/PrefectHQ/prefect/pull/10002>

### Documentation

- Resolve missing image in Prefect Cloud event documentation — <https://github.com/PrefectHQ/prefect/pull/9904>
- Fix typo in webhooks documentation — <https://github.com/PrefectHQ/prefect/pull/10003>

### Integrations

- Fix bug in `KubernetesWorker` where flow runs crashed during submission - <https://github.com/PrefectHQ/prefect-kubernetes/pull/76>

### Contributors

- @kkdenk made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9904>
- @rito-sixt

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.15...2.10.16>

## Release 2.10.15

## Introducing deployment configuration saving in `prefect deploy`

We are excited to announce a significant enhancement to our `prefect deploy` command to make your deployment process even more intuitive.

Previously, users had to recall their deployment configurations each time they wanted to redeploy with the same settings. Recognizing this potential inconvenience, we've now incorporated a feature to save your deployment inputs for future use, thereby streamlining redeployments.

The new interactive `prefect deploy` command guides you through the deployment process, from setting the schedule and the work pool to the `pull` step. After your deployment is created, you will have the option to save your inputs. Choosing "yes" will create a `prefect.yaml` file if one does not exist. The `prefect.yaml` file will contain your inputs stored in the deployments list and the generated `pull` step.

![saving with prefect deploy demo](https://github.com/PrefectHQ/prefect/assets/12350579/47d30cee-b0db-42c8-9d35-d7b25cd7856c)

If you have a `prefect.yaml` file in the same directory where you run your command, running the `deploy` command again allows you to reuse the saved deployment configuration or create a new one. If you choose to create a new deployment, you will again be given the option to save your inputs. This way, you can maintain a list of multiple deployment configurations, ready to be used whenever needed!

For more details on implementation, see the following pull request:

- <https://github.com/PrefectHQ/prefect/pull/9948>

### Fixes

- Fix error in `prefect deploy` when `.prefect` folder is absent — <https://github.com/PrefectHQ/prefect/pull/9972>
- Fix use of deprecated `git_clone_project` — <https://github.com/PrefectHQ/prefect/pull/9978>
- Fix exception raised in `prefect init` command when no recipe is selected — <https://github.com/PrefectHQ/prefect/pull/9963>

### Documentation

- Fix broken deployments api-ref page — <https://github.com/PrefectHQ/prefect/pull/9965>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.14...2.10.15>

## Release 2.10.14

### Simplifying project-based deployments

We've now simplified deployment management even further by consolidating the `prefect.yaml` and `deployment.yaml` files and removing the creation of the `.prefect` folder when running `prefect init`. We've also deprecated the name `projects`, renaming steps that had `projects` in the name.

For example:

```yaml
pull:
    - prefect.projects.steps.git_clone_project:
        id: clone-step
        repository: https://github.com/org/repo.git
```

is now

```yaml
pull:
    - prefect.deployments.steps.git_clone:
        id: clone-step
        repository: https://github.com/org/repo.git
```

An example using the `prefect_gcp` library:

```yaml
build:
    - prefect_gcp.projects.steps.push_project_to_gcs:
        requires: prefect-gcp
        bucket: my-bucket
        folder: my-project
```

is now

```yaml
build:
    - prefect_gcp.deployments.steps.push_to_gcs:
        requires: prefect-gcp
        bucket: my-bucket
        folder: my-project
```

In addition, we've removed the need to use the `project` command group through the CLI. Now, instead of `prefect project init` you can simply run `prefect init`. To use a deployment configuration recipe during initialization, you no longer need to run a `prefect project` command. Running `prefect init` will guide you through an interactive experience to choose a recipe if you so desire.

![prefect init recipe interaction](https://github.com/PrefectHQ/prefect/assets/42048900/c2bea9b4-4e1f-4029-8772-50ecde6073a7)

We have also deprecated deploying a flow via flow name (`-f`), allowing a single, streamlined way to deploy.

```python
prefect deploy ./path/to/flow.py:flow-fn-name
```

See these pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/9887>
- <https://github.com/PrefectHQ/prefect/pull/9930>
- <https://github.com/PrefectHQ/prefect/pull/9928>
- <https://github.com/PrefectHQ/prefect/pull/9944>
- <https://github.com/PrefectHQ/prefect/pull/9942>
- <https://github.com/PrefectHQ/prefect/pull/9957>
- <https://github.com/PrefectHQ/prefect-gcp/pull/189>
- <https://github.com/PrefectHQ/prefect-aws/pull/278>

### Prefect Cloud Webhook CLI

[Webhooks on Prefect Cloud](https://docs.prefect.io/2.10.14/cloud/webhooks/) allow you to capture events from a wide variety of sources in your data stack, translating them into actionable Prefect events in your workspace. Produce Prefect events from any system that can make an HTTP request and use those events in automations or to trigger event-driven deployments.

Even if you have minimal control over the systems you're integrating with, Prefect Cloud webhooks give you [full programmable control](https://docs.prefect.io/2.10.14/cloud/webhooks/#webhook-templates) over how you transform incoming HTTP requests into Prefect events with Jinja2 templating.  We even have a [built-in preset for CloudEvents](https://docs.prefect.io/2.10.14/cloud/webhooks/#accepting-cloudevents).

Webhooks are currently available [via the API and `prefect` CLI](https://docs.prefect.io/2.10.14/cloud/webhooks/#configuring-webhooks).

You can create your first Cloud webhook via the CLI like so:

```bash
prefect cloud webhook create your-webhook-name \
    --description "Receives webhooks from your system" \
    --template '{ "event": "your.event.name", "resource": { "prefect.resource.id": "your.resource.id" } }'
```

See the following pull request for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/9874>

### Enhancements

- Make related automations visible from `prefect deployment inspect` — <https://github.com/PrefectHQ/prefect/pull/9929>
- Enable deleting blocks with Python SDK — <https://github.com/PrefectHQ/prefect/pull/9932>
- Enhance ability to delete a single flow on the flows page - <https://github.com/PrefectHQ/prefect-ui-library/pull/1478>
- Add `work_pool_name` to work queue API responses — <https://github.com/PrefectHQ/prefect/pull/9659>
- Add httpx request method to Prefect Cloud client — <https://github.com/PrefectHQ/prefect/pull/9873>
- Mark flow as crashed if infrastructure submission fails — <https://github.com/PrefectHQ/prefect/pull/9691>
- Re-enable the retrieval of existing clients from flow and task run contexts when safe — <https://github.com/PrefectHQ/prefect/pull/9880>
- Add `prefect --prompt/--no-prompt` to force toggle interactive CLI sessions — <https://github.com/PrefectHQ/prefect/pull/9897>
- Return sorted task run ids when inspecting concurrency limit via CLI — <https://github.com/PrefectHQ/prefect/pull/9711>
- Use existing thread in `BatchedQueueService` to reduce queue retrieval overhead — <https://github.com/PrefectHQ/prefect/pull/9877>

### Fixes

- Provide a default `DTSTART` to anchor `RRULE` schedules to ensure extra schedules not created — <https://github.com/PrefectHQ/prefect/pull/9872>
- Fix bug where attribute error raised on service shutdown when the app startup fails — <https://github.com/PrefectHQ/prefect/pull/9900>
- Improve retry behavior when SQLite database locked — <https://github.com/PrefectHQ/prefect/pull/9938>

### Documentation

- Add tip on `PREFECT_API_URL` setting for workers and agents — <https://github.com/PrefectHQ/prefect/pull/9882>
- Add deployment triggers documentation — <https://github.com/PrefectHQ/prefect/pull/9886>
- Add more detailed documentation to the engine api-ref — <https://github.com/PrefectHQ/prefect/pull/9924>
- Add note on matching on multiple resources when using automations — <https://github.com/PrefectHQ/prefect/pull/9867>
- Updates automations examples in docs — <https://github.com/PrefectHQ/prefect/pull/9952>
- Update Prefect Cloud users documentation on user settings — <https://github.com/PrefectHQ/prefect/pull/9920>
- Boost non-API docs pages to optimize search results — <https://github.com/PrefectHQ/prefect/pull/9854>
- Update testing documentation tag — <https://github.com/PrefectHQ/prefect/pull/9905>
- Exemplify how to import Prefect client — <https://github.com/PrefectHQ/prefect/pull/9671>

## Contributors

- @Hongbo-Miao
- @rito-sixt made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9711>
- @drpin2341 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9905>
- @amansal1 made their first contribution in <https://github.com/PrefectHQ/prefect-ui-library/pull/1478>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.13...2.10.14>

## Release 2.10.13

### Improvements to projects-based deployments

![prefect deploy output with interactive cron schedule](https://github.com/PrefectHQ/prefect/assets/12350579/c94f45e6-3b7a-4356-84cd-f36a29f0415c)

Project-based deployments are now easier to use, especially for first time users! You can now run `prefect deploy` without first initializing a project. If you run `prefect deploy` without a project initialized, the CLI will generate a default pull step that your worker can use to retrieve your flow code when executing scheduled flow runs. The prefect deploy command will also prompt you with scheduling options, making it even easier to schedule your flows!

See these two pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/9832>
- <https://github.com/PrefectHQ/prefect/pull/9844>

This release also adds two new deployment steps: `pip_install_requirements` and `run_shell_script`. Both of these are new 'utility' deployment steps that can be used to automate portions of your deployment process.

Use the `pip_install_requirements` step to install Python dependencies before kicking off a flow run:

```yaml
pull:
    - prefect.projects.steps.git_clone_project:
        id: clone-step
        repository: https://github.com/org/repo.git
    - prefect.projects.steps.pip_install_requirements:
        directory: {{ clone-step.directory }}
        requirements_file: requirements.txt
        stream_output: False
```

Use the `run_shell_script` step to grab your repository's commit hash and use it to tag your Docker image:

```yaml
build:
    - prefect.projects.steps.run_shell_script:
        id: get-commit-hash
        script: git rev-parse --short HEAD
        stream_output: false
    - prefect.projects.steps.build_docker_image:
        requires: prefect-docker
        image_name: my-image
        image_tag: "{{ get-commit-hash.stdout }}"
        dockerfile: auto
```

See these two pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/9810>
- <https://github.com/PrefectHQ/prefect/pull/9868>

### Enhancements

- Allow project `pull` steps to pass step outputs — <https://github.com/PrefectHQ/prefect/pull/9861>
- Update work queue health indicators in Prefect UI for greater clarity - <https://github.com/PrefectHQ/prefect-ui-library/pull/1464>
- State messages no longer include tracebacks — <https://github.com/PrefectHQ/prefect/pull/9835>
- Allow passing a payload to `emit_instance_method_called_event` - <https://github.com/PrefectHQ/prefect/pull/9869>

### Fixes

- Reference `.prefectignore` files when moving files around locally to - <https://github.com/PrefectHQ/prefect/pull/9863>
- Fix typo in warning message raised when flow is called during script loading — <https://github.com/PrefectHQ/prefect/pull/9817>
- Allow creation of identical block names between different block types - <https://github.com/PrefectHQ/prefect-ui-library/pull/1473>
- Ensure flow timeouts do not override existing alarm signal handlers — <https://github.com/PrefectHQ/prefect/pull/9835>
- Ensure timeout tracking begins from the actual start of the call, rather than the scheduled start — <https://github.com/PrefectHQ/prefect/pull/9835>
- Ensure timeout monitoring threads immediately exit upon run completion — <https://github.com/PrefectHQ/prefect/pull/9835>
- Fix bug where background services could throw logging errors on interpreter exit — <https://github.com/PrefectHQ/prefect/pull/9835>
- Fix bug where asynchronous timeout enforcement could deadlock — <https://github.com/PrefectHQ/prefect/pull/9835>

### Documentation

- Add documentation on Prefect Cloud webhook usage - <https://github.com/PrefectHQ/prefect/pull/9857>
- Fix broken link and Prefect server reference in Cloud docs — <https://github.com/PrefectHQ/prefect/pull/9820>
- Fix broken link to Docker guide in API reference docs — <https://github.com/PrefectHQ/prefect/pull/9821>
- Update subflow run cancellation information in flows concept doc — <https://github.com/PrefectHQ/prefect/pull/9753>
- Improve ability to give feedback on documentation — <https://github.com/PrefectHQ/prefect/pull/9836>
- Add projects deployment diagram to work pool, workers & agents concept doc — <https://github.com/PrefectHQ/prefect/pull/9841>
- Add missing Prefect Server URL in API reference docs — <https://github.com/PrefectHQ/prefect/pull/9864>
- Fix code typo in task runners concept doc — <https://github.com/PrefectHQ/prefect/pull/9818>
- Add documentation on flow run parameter size limit — <https://github.com/PrefectHQ/prefect/pull/9847>
- Fix link to orchestration tutorial in execution tutorial - <https://github.com/PrefectHQ/prefect/pull/9862>

### Contributors

- @ac1997 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9862>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.12...2.10.13>

## Release 2.10.12

### The deployments page is back

We got a lot of positive feedback about the new flows page that was redesigned to include deployments, but several users pointed out that the it wasn't quite a full replacement for the dedicated deployments page. The deployments page has been re-added to the navigation menu until the new flows page is a worthy substitute.

See the [pull request](https://github.com/PrefectHQ/prefect/pull/9800) for implementation details.

### Enhancements

- All server-side schemas now have dedicated client-side duplicates — <https://github.com/PrefectHQ/prefect/pull/9577>
- Import of `prefect.server` is delayed to improve CLI start time and `import prefect` time — <https://github.com/PrefectHQ/prefect/pull/9577>
- Add task run as a related object to emitted events — <https://github.com/PrefectHQ/prefect/pull/9759>
- Emit task run state change events when orchestrating a task run — <https://github.com/PrefectHQ/prefect/pull/9684>
- Add healthcheck webserver to workers — <https://github.com/PrefectHQ/prefect/pull/9687>
- Create files and directories with user-scoped permissions — <https://github.com/PrefectHQ/prefect/pull/9789>
- Runtime variables mocked with environment variables for testing are now coerced to the correct type — <https://github.com/PrefectHQ/prefect/pull/9561>

### Fixes

- Show 404 instead of blank page in UI flow run id is invalid or if flow run is missing — <https://github.com/PrefectHQ/prefect/pull/9746>
- Fix bug where event loop shutdown hooks could fail due to early garbage collection — <https://github.com/PrefectHQ/prefect/pull/9748>
- Fix process worker `documentation_url` — <https://github.com/PrefectHQ/prefect/pull/9791>
- Fix bug where given priority was ignored when creating a work queue — <https://github.com/PrefectHQ/prefect/pull/9798>
- Fix inconsistent work queue handling by agent when cancelling flow runs — <https://github.com/PrefectHQ/prefect/pull/9757>

### Experimental

- Add `dashboard` experiment via `ENABLE_WORKSPACE_DASHBOARD` — <https://github.com/PrefectHQ/prefect/pull/9802>, <https://github.com/PrefectHQ/prefect/pull/9799>

### Deprecations

- Deprecate `create_orion_api` in favor of `create_api_app` — <https://github.com/PrefectHQ/prefect/pull/9745>
- Deprecate "send_to_orion" logging option in favor of "send_to_api" — <https://github.com/PrefectHQ/prefect/pull/9743>

### Documentation

- Add descriptions to concept tables — <https://github.com/PrefectHQ/prefect/pull/9718>
- Removes unreferenced requests import in 'real-world example' — <https://github.com/PrefectHQ/prefect/pull/9760>
- Add state change hooks to guides overview page — <https://github.com/PrefectHQ/prefect/pull/9761>
- Fix typo in flows and tasks tutorials — <https://github.com/PrefectHQ/prefect/pull/9762>
- Update task docs to reference common params and link to all params — <https://github.com/PrefectHQ/prefect/pull/9787>
- Add Google Analytics to documentation — <https://github.com/PrefectHQ/prefect/pull/9793>
- Remove outdated announcement — <https://github.com/PrefectHQ/prefect/pull/9792>
- Add extra loggers example — <https://github.com/PrefectHQ/prefect/pull/9714>
- Clarify work pool priority options — <https://github.com/PrefectHQ/prefect/pull/9752>
- Update worker requirements in projects tutorial — <https://github.com/PrefectHQ/prefect/pull/9579>
- Fix default value comment in docs/concepts/variables — <https://github.com/PrefectHQ/prefect/pull/9771>
- Fix formatting of link to Ray page — <https://github.com/PrefectHQ/prefect/pull/9772>
- Add book a rubber duck links — <https://github.com/PrefectHQ/prefect/pull/9790>

### Contributors

- @marco-buttu made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9771>
- @jcozar87 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9561>
- @rmorshea

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.11...2.10.12>

## Release 2.10.11

### Interactive Deployments and Work Pool Wizard 🧙

This release simplifies deployment and work pool creation.

![interactive-prefect-deploy-console-output](https://github.com/PrefectHQ/prefect/assets/12350579/c861b8dd-2dbb-4cfa-82f9-69008714f9fe)

Firstly, the `prefect deploy` command has been upgraded to provide interactive prompts for deployment names and work pool selections. If you don't provide a deployment name via the CLI or a `deployment.yaml` file, the CLI will prompt you to do so. Furthermore, if a work pool name isn't specified, the CLI will guide you through the available work pools for your workspace. This feature aims to make deployments more approachable, especially for first-time users, requiring just an entrypoint to a flow to get started.

![work-pool-wizard-infrastructure-choices](https://github.com/PrefectHQ/prefect/assets/12350579/383f004b-816e-4a52-98c3-46745e273362)

Secondly, we've added a work pool creation wizard to streamline the process and spotlight various infrastructure types. The wizard will walk you through the essentials: basic work pool info, infrastructure type, and infrastructure configuration. The infrastructure type step will present you with a list of available infrastructure types, each with an icon and a description.

Together, these improvements offer an interactive, guided experience that not only simplifies deployments and work pool creation but also empowers users to navigate the process confidently and efficiently.

Check out these pull requests for more details:

- <https://github.com/PrefectHQ/prefect-ui-library/pull/1431>
- <https://github.com/PrefectHQ/prefect/pull/9707>
- <https://github.com/PrefectHQ/prefect/pull/9686>

### Enhancements

- Emit events from deployments, work queues, and work pools — <https://github.com/PrefectHQ/prefect/pull/9635>
- Improve SQLite database transaction behavior — <https://github.com/PrefectHQ/prefect/pull/9594>
- Add support for SQLAlchemy 2 — <https://github.com/PrefectHQ/prefect/pull/9656>
- Add `on_cancellation` flow run state change hook — <https://github.com/PrefectHQ/prefect/pull/9389>
- Improve cancellation cleanup service iteration over subflow runs - <https://github.com/PrefectHQ/prefect/pull/9731>
- Add request retry support to Prefect Cloud client — <https://github.com/PrefectHQ/prefect/pull/9724>
- Add `PREFECT_CLIENT_MAX_RETRIES` for configuration of maximum HTTP request retries - <https://github.com/PrefectHQ/prefect/pull/9735>
- Add an `/api/ready` endpoint to the Prefect server to check database connectivity — <https://github.com/PrefectHQ/prefect/pull/9701>
- Display URL to flow run on creation - <https://github.com/PrefectHQ/prefect/pull/9740>
- Add guard against changing the profile path from `prefect config set` — <https://github.com/PrefectHQ/prefect/pull/9696>
- Use flow run logger to report traceback for failed submissions — <https://github.com/PrefectHQ/prefect/pull/9733>
- Improve default Prefect image tag when using development versions — <https://github.com/PrefectHQ/prefect/pull/9503>
- Emit worker event when a flow run is scheduled to run or cancel — <https://github.com/PrefectHQ/prefect/pull/9702>
- Add ability to filter for `Retrying` state in the Task Runs tab of the Prefect UI — <https://github.com/PrefectHQ/prefect-ui-library/pull/1410>

### Fixes

- Display CLI deprecation warnings to STDERR instead of STDOUT — <https://github.com/PrefectHQ/prefect/pull/9690>
- Fix hanging flow runs from deployments when variables retrieved in base scope - <https://github.com/PrefectHQ/prefect/pull/9665>
- Fix maximum character length when updating variables — <https://github.com/PrefectHQ/prefect/pull/9710>
- Fix bug where agents would fail when processing runs with deleted deployments — <https://github.com/PrefectHQ/prefect/pull/9464>
- Fix bug where `uvicorn` could not be found when server was started from an unloaded virtual environment - <https://github.com/PrefectHQ/prefect/pull/9734>
- Allow table artifacts `table` argument as list of lists — <https://github.com/PrefectHQ/prefect/pull/9732>
- Fix bug where events worker would fail if the API URL includes a trailing `/` — <https://github.com/PrefectHQ/prefect/pull/9663>
- Fix bug where flow run timeline crashed when custom state names were used — <https://github.com/PrefectHQ/prefect-ui-library/pull/1448>

### Collections

- Stream Kubernetes Worker flow run logs to the API - [#72](https://github.com/PrefectHQ/prefect-kubernetes/pull/72)
- Stream ECS Worker flow run logs to the API - [#267](https://github.com/PrefectHQ/prefect-aws/pull/267)
- Stream Cloud Run Worker flow run logs logs to the API - [#183](https://github.com/PrefectHQ/prefect-gcp/pull/183)
- Add `prefect-spark-on-k8s-operator` to integrations catalog list — [#9029](https://github.com/PrefectHQ/prefect/pull/9029)
- Add optional `accelerator_count` property for `VertexAICustomTrainingJob` - [#174](https://github.com/PrefectHQ/prefect-gcp/pull/174)
- Add `result_transformer` parameter to customize the return structure of `bigquery_query` - [#176](https://github.com/PrefectHQ/prefect-gcp/pull/176)
- Add `boot_disk_type` and `boot_disk_size_gb` properties for `VertexAICustomTrainingJob` - [#177](https://github.com/PrefectHQ/prefect-gcp/pull/177)
- Fix bug where incorrect credentials model was selected when `MinIOCredentials` was used with `S3Bucket` - [#254](https://github.com/PrefectHQ/prefect-aws/pull/254)
- Fix bug where `S3Bucket.list_objects` was truncating prefix paths ending with slashes - [#263](https://github.com/PrefectHQ/prefect-aws/pull/263)
- Fix bug where ECS worker could not cancel flow runs - [#268](https://github.com/PrefectHQ/prefect-aws/pull/268)
- Improve failure message when creating a Kubernetes job fails - [#71](https://github.com/PrefectHQ/prefect-kubernetes/pull/71)

### Deprecations

- Rename `prefect.infrastructure.docker` to `prefect.infrastructure.container` - <https://github.com/PrefectHQ/prefect/pull/8788>
- Rename `prefect.docker` to `prefect.utilities.dockerutils` - <https://github.com/PrefectHQ/prefect/pull/8788>

### Documentation

- Create examples of working with Prefect REST APIs — <https://github.com/PrefectHQ/prefect/pull/9661>
- Add state change hook documentation - <https://github.com/PrefectHQ/prefect/pull/9721>
- Add tip about private repositories in projects documentation — <https://github.com/PrefectHQ/prefect/pull/9685>
- Improve runtime context documentation — <https://github.com/PrefectHQ/prefect/pull/9652>
- Simplify the flow and task configuration documentation — <https://github.com/PrefectHQ/prefect/pull/9420>
- Clarify task retries documentation — <https://github.com/PrefectHQ/prefect/pull/9575>
- Fix typos in cloud documentation — <https://github.com/PrefectHQ/prefect/pull/9657>
- Update automations documentation — <https://github.com/PrefectHQ/prefect/pull/9680>
- Fix typo in tutorial documentation — <https://github.com/PrefectHQ/prefect/pull/9646>
- Add tip on `keys` in artifacts documentation — <https://github.com/PrefectHQ/prefect/pull/9666>
- Expand docstrings for artifacts — <https://github.com/PrefectHQ/prefect/pull/9704>
- Update description of `image` parameter of `DockerContainer` in infrastructure documentation — <https://github.com/PrefectHQ/prefect/pull/9682>
- Lowercase Prefect server where appropriate — <https://github.com/PrefectHQ/prefect/pull/9697>
- Remove `Upgrading from Prefect Beta` section of installation page — <https://github.com/PrefectHQ/prefect/pull/9726>
- Update rate limit documentation to include `/set_state` and `/flows` endpoint for Prefect Cloud — <https://github.com/PrefectHQ/prefect/pull/9694>
- Update documentation links in UI to concepts when possible — <https://github.com/PrefectHQ/prefect-ui-library/pull/1351>

## Contributors

- @BitTheByte

- @snikch made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9646>
- @rkscodes made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9682>
- @sarahmk125 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9694>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.10...2.10.11>

## Release 2.10.10

### The need for (CLI) speed

We wanted the CLI to be as fast as the rest of Prefect. Through a series of enhancements, we've sped up CLI performance by as much as 4x on some systems!

See the following pull requests for implementation details:

- Delay `apprise` imports — <https://github.com/PrefectHQ/prefect/pull/9557>
- Defer import of `dateparser` — <https://github.com/PrefectHQ/prefect/pull/9582>
- Defer loading of Prefect integrations until necessary — <https://github.com/PrefectHQ/prefect/pull/9571>
- Add `Block.get_block_class_from_key` and replace external uses of `lookup_type` — <https://github.com/PrefectHQ/prefect/pull/9621>
- Load collections before auto-registering block types on the server — <https://github.com/PrefectHQ/prefect/pull/9626>
- Do not restrict deployment build infrastructure types to types known at import time — <https://github.com/PrefectHQ/prefect/pull/9625>

### Enhancements

- Handle `SIGTERM` received by workers gracefully — <https://github.com/PrefectHQ/prefect/pull/9530>
- Add ability to view table artifacts with NaN values in the Prefect UI — <https://github.com/PrefectHQ/prefect/pull/9585>
- Update `prefect version` command to avoid creating the database if it does not exist — <https://github.com/PrefectHQ/prefect/pull/9586>
- Allow client retries when server SQLite database is busy — <https://github.com/PrefectHQ/prefect/pull/9632>
- Allow client retries when general database errors are encountered — <https://github.com/PrefectHQ/prefect/pull/9633>
- Ensure published Docker images have latest versions of requirements — <https://github.com/PrefectHQ/prefect/pull/9640>

### Fixes

- Fix bug where `SIGTERM` was not properly captured as a flow run crash for flow runs created by a deployment — <https://github.com/PrefectHQ/prefect/pull/9543>
- Fix deadlock when logging is overridden from an asynchronous context — <https://github.com/PrefectHQ/prefect/pull/9602>
- Fix orchestration race conditions by adding lock for update to flow run state transitions — <https://github.com/PrefectHQ/prefect/pull/9590>
- Fix date range filter on flow runs page — <https://github.com/PrefectHQ/prefect/pull/9636>
- Fix bug where ephemeral server raised exceptions client-side — <https://github.com/PrefectHQ/prefect/pull/9637>
- Fix bug where ARM64 Docker images had a corrupt database — <https://github.com/PrefectHQ/prefect/pull/9587>

### Documentation

- Clarify the retry on tasks concept page — <https://github.com/PrefectHQ/prefect/pull/9560>
- Improve the navigation structure and clarity of the API docs — <https://github.com/PrefectHQ/prefect/pull/9574>
- Add `work_pool_name` to `Deployment.build_from_flow` on deployments concept page — <https://github.com/PrefectHQ/prefect/pull/9581>
- Add additional worker types to work pools, workers & agents concept page — <https://github.com/PrefectHQ/prefect/pull/9580>
- Add docstrings for all schema filters — <https://github.com/PrefectHQ/prefect/pull/9572>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.9...2.10.10>

## Release 2.10.9

### Worker logs can now be seen on the flow run page

Workers now link relevant logs to specific flow runs, allowing you to view infrastructure-related logs on your flow run page.

<img width="1294" alt="Process worker logs" src="https://github.com/PrefectHQ/prefect/assets/2586601/658c2883-69f7-4ee0-abf6-a20ee4723b3a">

You'll see generic logs from all worker types. Integration worker implementations such as Kubernetes workers will be updated to send additional rich logs to give you insight into the behavior of flow run infrastructure.

See <https://github.com/PrefectHQ/prefect/pull/9496> for details.

### Enhancements

- Handle `SIGTERM` received by agent gracefully — <https://github.com/PrefectHQ/prefect/pull/8691>
- Add global default settings for flow and task retries and retry delay seconds — <https://github.com/PrefectHQ/prefect/pull/9171>
- Add support for populating submodules to `git_clone_project` projects step — <https://github.com/PrefectHQ/prefect/pull/9504>
- Add wrapper for exceptions encountered while resolving parameter inputs — <https://github.com/PrefectHQ/prefect/pull/8584>
- Add flush of logs before exiting deployed flow run processes to ensure messages are not lost — <https://github.com/PrefectHQ/prefect/pull/9516>
- Update worker to be able to include itself as a related resource — <https://github.com/PrefectHQ/prefect/pull/9531>

### Fixes

- Fix bug where `SIGTERM` was not properly captured as a flow run crash — <https://github.com/PrefectHQ/prefect/pull/9498>
- Fix pass of optional parameters to API in `client.create_work_queue` — <https://github.com/PrefectHQ/prefect/pull/9521>

### Documentation

- Add tip about flow run level concurrency — <https://github.com/PrefectHQ/prefect/pull/9490>
- Add documentation on `on_failure` flow run state change hook — <https://github.com/PrefectHQ/prefect/pull/9511>
- Update tutorials landing page — <https://github.com/PrefectHQ/prefect/pull/9450>

### Contributors

- @andrewbrannan made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9521>

- @ddelange

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.8...2.10.9>

## Release 2.10.8

### Flow run orchestration rule updates

A flow run orchestration rule which was previously intended to prevent backwards transitions is updated in this release to allow most transitions. Now, it only prevents some transitions to `PENDING` states to prevent race conditions during handling of runs by multiple agents or workers. This improves orchestration behavior during infrastructure restarts. For example, when a Kubernetes pod is interrupted, the flow run can be rescheduled on a new pod by Kubernetes. Previously, Prefect would abort the run as it attempted to transition from a `RUNNING` to a `RUNNING` state. Now, Prefect will allow this transition and your flow run will continue.

In summary, the following rules apply now:

- `CANCELLED` -> `PENDING` is not allowed
- `CANCELLING`/`RUNNING` -> `RUNNING` is allowed
- `CANCELLING`/`RUNNING`/`PENDING` -> `SCHEDULED` is allowed

See <https://github.com/PrefectHQ/prefect/pull/9447> for details.

### Enhancements

- Display message when service back-off is reset to avoid confusion — <https://github.com/PrefectHQ/prefect/pull/9463>
- Improve `QueueService` performance — <https://github.com/PrefectHQ/prefect/pull/9481>

### Fixes

- Ensure deployment creation does not require write access when a prefectignore file exists — <https://github.com/PrefectHQ/prefect/pull/9460>
- Fix bug where `deployment apply` command could hang on exit — <https://github.com/PrefectHQ/prefect/pull/9481>

### Deprecations

- Add future warning for Python 3.7 EOL — <https://github.com/PrefectHQ/prefect/pull/9469>

### Documentation

- Move creating a new worker type tutorial to guides — <https://github.com/PrefectHQ/prefect/pull/9455>
- Fix `name` description in `deployment.yaml` reference — <https://github.com/PrefectHQ/prefect/pull/9461>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.7...2.10.8>

## Release 2.10.7

### New and improved Flows page

This release combines the previously separate flows and deployments UI pages into a single, holistic page that brings together flows and deployments, as well as their recent and upcoming runs. You can now see the state of the most recent flow run for each flow and deployment, giving you a snapshot of the status of your workspace. In addition, you can now filter deployments by whether their schedule is active and the work pool to which flow runs are submitted. See <https://github.com/PrefectHQ/prefect/pull/9438> for details.

![flows-page](https://user-images.githubusercontent.com/3407835/236275227-04944fde-cdc2-4f44-bcae-eb65f4cafa0d.png)

### `on_crashed` state change hook for flows

This release introduces the new `on_crashed` hook for flows, allowing you to add client-side hooks that will be called when your flow crashes. This is useful for cases where you want to execute code without involving the Prefect API, and for custom handling on `CRASHED` terminal states. This callable hook will receive three arguments: `flow`, `flow_run`, and `state`.

Here is an example of how to use the `on_crashed` hook in your flow:

```python
from prefect import flow

def crash_hook(flow, flow_run, state):
    print("Don't Panic! But the flow has crashed...")

@flow(on_crashed=[crash_hook])
def my_flow():
    # call `crash_hook` if this flow enters a `CRASHED` state
    pass

if __name__ == '__main__':
    my_flow()
```

Now, if your flow crashes, `crash_hook` will be executed! Notably, you can also call the same hook for a variety of terminal states, or call multiple hooks for the same terminal state. For example:

```python
@flow(on_crashed=[my_hook], on_failure=[my_hook])
def my_flow():
   # call the same hook if this flow enters a `FAILED` or `CRASHED` state
   pass

@flow(on_crashed=[my_first_hook, my_second_hook])
def my_flow():
   # call two different hooks if this flow enters a `CRASHED` state
   pass
```

See the [pull request](https://github.com/PrefectHQ/prefect/pull/9418) for implementation details.

### Enhancements

- Prevent unnecessarily verbose logs by updating `log_prints` to ignore prints where a custom `file` is used — <https://github.com/PrefectHQ/prefect/pull/9358>
- Create a process work pool by default when a new worker is started with a new work pool name and no type — <https://github.com/PrefectHQ/prefect/pull/9326>
- Add support for asynchronous project steps — <https://github.com/PrefectHQ/prefect/pull/9388>
- Update `critical_service_loop` to retry on all 5XX HTTP status codes — <https://github.com/PrefectHQ/prefect/pull/9400>
- Add backoff on failure to agent critical loop services — <https://github.com/PrefectHQ/prefect/pull/9402>
- Add print statement to `git pull` to isolate issues between clone and execution — <https://github.com/PrefectHQ/prefect/pull/9328>
- Add `on_crashed` flow run state change hook — <https://github.com/PrefectHQ/prefect/pull/9418>
- Make build->push step explicit in docker project recipes — <https://github.com/PrefectHQ/prefect/pull/9417>
- Add storage blocks to cli `deployment build` help description  — <https://github.com/PrefectHQ/prefect/pull/9411>
- Add `call_in_...` methods to the concurrency API — <https://github.com/PrefectHQ/prefect/pull/9415>
- Add support for `Callable[[], T]` to concurrency API methods — <https://github.com/PrefectHQ/prefect/pull/9413>
- Add a parameters JSON input option for deployments in the UI — [`#1405`](https://github.com/PrefectHQ/prefect-ui-library/pull/1405)
- Improve consistency in UI help modals — [`#1397`](https://github.com/PrefectHQ/prefect-ui-library/pull/1397)

### Fixes

- Add guard against null schedule in `deployment.yaml` — <https://github.com/PrefectHQ/prefect/pull/9373>
- Fix issue preventing work pool filter from being applied to the flow runs page — <https://github.com/PrefectHQ/prefect/pull/9390>
- Fix project recipe `image_name` and `tag` templating in docker-git, docker-gcs, and docker-s3 — <https://github.com/PrefectHQ/prefect/pull/9425>
- Fix bug with work queues showing as unhealthy when a work queue with the same name is unhealthy — <https://github.com/PrefectHQ/prefect/pull/9437>
- Fix bug where child flows would not fail the parent when they received invalid arguments — <https://github.com/PrefectHQ/prefect/pull/9386>
- Fix schema values mapping on the create flow run forms to ensure all parameter values can be edited — [`#1407`](https://github.com/PrefectHQ/prefect-ui-library/pull/1407)
- Add a check for color scheme to ensure the flow run state favicon is visible — [`#1392`](https://github.com/PrefectHQ/prefect-ui-library/pull/1392)
- Fix deadlock during API log handler flush when logging configuration is overridden — <https://github.com/PrefectHQ/prefect/pull/9354>
- Fix send/drain race conditions in queue services — <https://github.com/PrefectHQ/prefect/pull/9426>
- Fix bug where missing trailing slash in remote filesystems path would cause download failures — <https://github.com/PrefectHQ/prefect/pull/9440>

### Documentation

- Add a link to bug bounty program information — <https://github.com/PrefectHQ/prefect/pull/9366>
- Add `Additional Resources` Section to Work Pools, Workers, & Agents page — <https://github.com/PrefectHQ/prefect/pull/9393>
- Fix mistaken placement of `result_storage` parameter — <https://github.com/PrefectHQ/prefect/pull/9422>
- Add concept list to concept section parent page — <https://github.com/PrefectHQ/prefect/pull/9404>
- Add Paused and Cancelling states to states concept page — <https://github.com/PrefectHQ/prefect/pull/9435>
- Update docs logos — <https://github.com/PrefectHQ/prefect/pull/9365>
- Direct _Prefect Integration template_ link to the correct page — <https://github.com/PrefectHQ/prefect/pull/9362>
- Update landing page image — <https://github.com/PrefectHQ/prefect/pull/9448>

### New Contributors

- @rmorshea made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9422>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.6...2.10.7>

## Release 2.10.6

### Deploy many flows at once with projects

You can now declare multiple deployments for your project in the `deployment.yaml` file. When multiple deployments are declared in a project, you can deploy any number of those deployments at a time by providing the names of the deployments in the `prefect deploy` command. You can also deploy all the deployments in a project with the `--all` flag on the `prefect deploy` command.

Deployments that are declared in a project are independent of each other and can be deployed to different work pools, on different schedules, or using different project actions. By default, deployments will use the build, pull, and push actions defined in the projects `prefect.yaml` file, but those actions can be overridden by setting build, pull, or push on a deployment declared in `deployment.yaml`. This enables patterns like different project storage methods and multiple Dockerfiles for a project.

Because the deployments are all declared in a single YAML file, you can also take advantage of YAML anchors and aliases to avoid duplication in your `deployment.yaml` file. This enables declaring custom projects actions once and reusing them across different deployments or using the same schedule for multiple deployments.
To learn more about Projects, check out our [documentation](https://docs.prefect.io/latest/concepts/projects/) and [tutorials](https://docs.prefect.io/latest/tutorials/projects/) to quickly accelerate your flow deployment process!
See <https://github.com/PrefectHQ/prefect/pull/9217> for details.

### Improve run restart behavior

Previously, transitions out of terminal states were allowed in very specific cases:

- A task run could move from a failed/crashed/cancelled state to running if the flow run was retrying
- A flow run could move to a scheduled (awaiting retry) state

These rules could prevent runs from executing again during manual restarts or worker rescheduling.  We now allow transitions out of terminal states unless the run is completed _and_ has a persisted result to improve our behavior during these cases.

For example, these changes enable the following behaviors:

- A task run that fails and is orchestrated again will run instead of aborting
- A task run that completes but does not persist its result will run again on flow run retry
- A flow run may be rescheduled without using the "awaiting retry" name
- A flow run that fails and is orchestrated again will run instead of aborting

See <https://github.com/PrefectHQ/prefect/pull/9152> for details.

### Enhancements

- Add support for recursive flow calls — <https://github.com/PrefectHQ/prefect/pull/9342>
- Add support for concurrent runs same flow — <https://github.com/PrefectHQ/prefect/pull/9342>
- Add ability for `flow_run_name` and `task_run_name` settings to accept functions — <https://github.com/PrefectHQ/prefect/pull/8933>
- Add pending items count to service failure exception message — <https://github.com/PrefectHQ/prefect/pull/9306>
- Add `severity` key to JSON-formatted logs for GCP compatibility — <https://github.com/PrefectHQ/prefect/pull/9200>
- Update orchestration rules to allow transitions from terminal states — <https://github.com/PrefectHQ/prefect/pull/9152>
- Enable filtering flows by work pool at the `/flows/filter` endpoint — <https://github.com/PrefectHQ/prefect/pull/9308>
- Add `--tail` option to `prefect flow-run logs` CLI — <https://github.com/PrefectHQ/prefect/pull/9028>
- Enhance UI handling of flow run graph and accompanying selection panel — <https://github.com/PrefectHQ/prefect/pull/9333>
- Enhance UI rendering of schema-generated forms (used for flow run creation, deployment editing, block configuration, notifications, and work pool job templates) and their values — <https://github.com/PrefectHQ/prefect-ui-library/pull/1384>
- Update icons and Prefect logo — <https://github.com/PrefectHQ/prefect/pull/9352>
- Add results to task run page — <https://github.com/PrefectHQ/prefect-ui-library/pull/1372>
- Add artifacts to task run page — <https://github.com/PrefectHQ/prefect/pull/9353>
- Show entrypoint and path in deployment details — <https://github.com/PrefectHQ/prefect-ui-library/pull/1364>
- Enhance clarity of error message by raising `UnfinishedRun` instead of `MissingResult` when state is not final — <https://github.com/PrefectHQ/prefect-ui-library/pull/9334>

### Fixes

- Ensure the Prefect UI displays actual parameters used to kick off a flow run — <https://github.com/PrefectHQ/prefect/pull/9293>
- Ensure workers only create one client while running — <https://github.com/PrefectHQ/prefect/pull/9302>
- Ensure services are drained on global loop shutdown — <https://github.com/PrefectHQ/prefect/pull/9307>
- Show logs on pending flow run pages — <https://github.com/PrefectHQ/prefect/pull/9313>
- Fix `flow-run logs --limit` — <https://github.com/PrefectHQ/prefect/pull/9314>
- Fix `future.result()` and `future.wait()` calls from async contexts — <https://github.com/PrefectHQ/prefect/pull/9316>
- Update `QueueService.send` to wait for the item to be placed in the queue before returning — <https://github.com/PrefectHQ/prefect/pull/9318>
- Update `resolve_futures_to_data` and `resolve_futures_to_states` to wait for futures in the correct event loop — <https://github.com/PrefectHQ/prefect/pull/9336>
- Fix bug where tasks were not called when debug mode was enabled — <https://github.com/PrefectHQ/prefect/pull/9341>
- Fix bug where boolean values for new flow runs created through the UI were not sent if the value matched the deployment's schema default — <https://github.com/PrefectHQ/prefect-ui-library/pull/1389>
- Fix race condition in event loop thread start — <https://github.com/PrefectHQ/prefect/pull/9343>

### Documentation

- Add tutorial for developing a new worker — <https://github.com/PrefectHQ/prefect/pull/9179>
- Fix social cards to enable previews when linking documentation — <https://github.com/PrefectHQ/prefect/pull/9321>
- Fix rendering of Prefect Server and Cloud feature list — <https://github.com/PrefectHQ/prefect/pull/9305>
- Fix a broken link and clarify language — <https://github.com/PrefectHQ/prefect/pull/9295>
- Update "Event Feed" screenshot — <https://github.com/PrefectHQ/prefect/pull/9349>

### New Contributors

- @rsampaths16 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8933>
- @Shubhamparashar made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9028>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.5...2.10.6>

## Release 2.10.5

### Deploy a Prefect flow via Github Actions

With the new [Deploy a Prefect flow](https://github.com/marketplace/actions/deploy-a-prefect-flow) GitHub Action, you can automate the build process for deployments orchestrated by Prefect Cloud. The action leverages the new [Projects](https://docs.prefect.io/latest/concepts/projects/) system. See the [action page](https://github.com/marketplace/actions/deploy-a-prefect-flow) for examples and configuration options.

### Cloud Provider Workers

Workers, Prefect's next-generation agents, have dedicated infrastructure types. This week, we are releasing typed workers for each major cloud provider: AWS, GCP, and Azure. You will be able to find them in the [prefect-aws](https://github.com/PrefectHQ/prefect-aws), [prefect-gcp](https://prefecthq.github.io/prefect-gcp/), and [prefect-azure](https://github.com/PrefectHQ/prefect-azure) collections, respectively.

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect-aws/pull/238>
- <https://github.com/PrefectHQ/prefect-aws/pull/244>
- <https://github.com/PrefectHQ/prefect-gcp/pull/172>
- <https://github.com/PrefectHQ/prefect-azure/pull/87>

### Enhancements

- Add `idempotency_key` to flow runs filter — [#8600](https://github.com/PrefectHQ/prefect/pull/8600)
- Add `details` tab to flow run page and increase flow run graph width — [#9258](https://github.com/PrefectHQ/prefect/pull/9258)
- Add status code to base client log on retry — [#9265](https://github.com/PrefectHQ/prefect/pull/9265)

### Fixes

- Fix issue in which work queues were duplicated in the `default-agent-pool` when creating a deployment — [#9046](https://github.com/PrefectHQ/prefect/pull/9046)
- Add `configuration` to `Worker.kill_infrastructure` signature — [#9250](https://github.com/PrefectHQ/prefect/pull/9250)
- Update `critical_service_loop` to throw a runtime error on failure — [#9267](https://github.com/PrefectHQ/prefect/pull/9267)
- Fix pip requirement inference compatibility with Python 3.11+ and pip 23.1+ — [#9278](https://github.com/PrefectHQ/prefect/pull/9278)
- Fix validation error occurring on default values in `variables` schema of `Workpool.base_job_template` [#9282](https://github.com/PrefectHQ/prefect/pull/9282)

### Experimental

- Add `worker.executed-flow-run` event — [#9227](https://github.com/PrefectHQ/prefect/pull/9227)
- Emit events for worker lifecycle — [#9249](https://github.com/PrefectHQ/prefect/pull/9249)
- Emit `cancelled-flow-run` event when worker cancels a flow run — [#9255](https://github.com/PrefectHQ/prefect/pull/9255)

### Documentation

- Fix broken link on docs landing page — [#9247](https://github.com/PrefectHQ/prefect/pull/9247)
- Remove outdated warning from task run concurrency UI docs — [#9256](https://github.com/PrefectHQ/prefect/pull/9256)
- Add `edit` button to docs to improve ability to fix documentation — [#9259](https://github.com/PrefectHQ/prefect/pull/9259)
- Remove UI documentation pages, reorganize content, and simplify side bar navigation structure — [#9039](https://github.com/PrefectHQ/prefect/pull/9039)
- Add tutorial for creating a worker — [#9179](https://github.com/PrefectHQ/prefect/pull/9179)
- Add GitHub Action to trigger versioned builds in docs repository — [#8984](https://github.com/PrefectHQ/prefect/pull/8984)

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.4...2.10.5>

## Release 2.10.4

This release further refines Prefect 2.10 with enhancements for [project deployments](https://docs.prefect.io/latest/concepts/projects/#the-deployment-yaml-file) and
[workers](https://docs.prefect.io/latest/concepts/work-pools/#worker-overview), fixes for flow run cancellation and the worker CLI, and more.

### More flexible project deployments

Prior to this release, removing keys from a project's `deployment.yaml` caused an error. Thanks to the changes in [#9190](https://github.com/PrefectHQ/prefect/pull/9190), Prefect now uses default values for any required keys missing from your project's configuration.

### Enhancements

- Allow partial `deployment.yaml` files for projects by using defaults for missing values — [#9190](https://github.com/PrefectHQ/prefect/pull/9190)
- Add flow run cancellation support for workers — [#9198](https://github.com/PrefectHQ/prefect/pull/9198)

### Fixes

- Prevent scheduled flow runs from getting stuck in `CANCELLING` state  — [#8414](https://github.com/PrefectHQ/prefect/pull/8414)
- Fix `work_queues` and `worker_type` arguments for the `prefect worker start` CLI command — [#9154](https://github.com/PrefectHQ/prefect/pull/9154)
- Fix overflow in flow run logger UI [`#1342`](https://github.com/PrefectHQ/prefect-ui-library/pull/1342)
- Fix schema form handling of reference objects [`#1332`](https://github.com/PrefectHQ/prefect-ui-library/pull/1332)
- Improve flow graph UX by suppressing shortcuts when a metakey is active [`#1333`](https://github.com/PrefectHQ/prefect-ui-library/pull/1333)

### Experimental

- Emit an event when a worker submits a flow run for execution — [#9203](https://github.com/PrefectHQ/prefect/pull/9203)

### Documentation

- Fix a broken link by removing an obsolete redirect — [#9189](https://github.com/PrefectHQ/prefect/pull/9189)
- Add polling interval information to worker and agent documentation — [#9209](https://github.com/PrefectHQ/prefect/pull/9209)
- Update documentation badge styling to improve docs usability — [#9207](https://github.com/PrefectHQ/prefect/pull/9207)

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.3...2.10.4>

## Release 2.10.3

This release builds on 2.10 to further improve the experience of setting up and deploying from [a prefect project](https://docs.prefect.io/latest/tutorials/projects/).  In particular, initializing with a recipe now initializes an interactive CLI experience that guides you to a correct setup.  This experience can be avoided for programmatic initialization by providing all required fields for the recipe via CLI.  For more information, see [the project documentation](https://docs.prefect.io/latest/concepts/projects/).  We will continue to enhance the deployment experience as we receive feedback, so please keep it coming!

This release also includes [a critical fix](https://github.com/PrefectHQ/prefect/pull/9180) for Prefect logs that were sometimes delayed in being sent to the API.

### Enhancements

- Rename `prefect.__root_path__` to `prefect.__development_base_path__` — <https://github.com/PrefectHQ/prefect/pull/9136>
- Include flow run and flow as related resources when emitting events via the events worker — <https://github.com/PrefectHQ/prefect/pull/9129>
- Improve Cloud storage Projects recipes — <https://github.com/PrefectHQ/prefect/pull/9145>
- Use new sessions and transactions for each query during `CancellationCleanup` — <https://github.com/PrefectHQ/prefect/pull/9124>
- Stream `git` output during `git_clone_project` — <https://github.com/PrefectHQ/prefect/pull/9149>
- Update deployment defaults with project init — <https://github.com/PrefectHQ/prefect/pull/9146>
- Add ability to mock `prefect.runtime` attributes via environment variable — <https://github.com/PrefectHQ/prefect/pull/9156>
- Add scheduling options to deploy CLI — <https://github.com/PrefectHQ/prefect/pull/9176>
- Add deployment and flow filters to `/artifacts/filter` and `/artifacts/latest/filter` routes — <https://github.com/PrefectHQ/prefect/pull/9089>
- Add `/artifacts/latest/count` route — <https://github.com/PrefectHQ/prefect/pull/9090>
- Add flow run metadata to task run logger — <https://github.com/PrefectHQ/prefect/pull/9170>
- Add pragma statements automatically if sqlite writing database migrations for SQLite — <https://github.com/PrefectHQ/prefect/pull/9169>
- Improve Projects `recipe` initialization UX — <https://github.com/PrefectHQ/prefect/pull/9158>

### Fixes

- Update `prefect deploy` to pull `flow_name` and `entrypoint` from deployment.yaml if specified — <https://github.com/PrefectHQ/prefect/pull/9157>
- Fix bug where non-zero status codes would be reported when deployed flow runs paused or failed — <https://github.com/PrefectHQ/prefect/pull/9175>
- Hide command when access token is provided and `git_clone_project` fails — <https://github.com/PrefectHQ/prefect/pull/9150>
- Fix bug where log worker only sent logs to API on flush rather than on an interval — <https://github.com/PrefectHQ/prefect/pull/9180>
- Fix apply artifact collection filter — <https://github.com/PrefectHQ/prefect/pull/9153>

### Documentation

- Add artifacts to API reference — <https://github.com/PrefectHQ/prefect/pull/9143>
- Expand upon Projects `steps` documentation — <https://github.com/PrefectHQ/prefect/pull/9151>

### Collections

- Add `prefect-spark-on-k8s-operator` to integrations catalog list — <https://github.com/PrefectHQ/prefect/pull/9029>

### Contributors

- @tardunge made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9029>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.2...2.10.3>

## Release 2.10.2

Fixes a bug where deployments were not downloaded from remote storage blocks during flow runs — <https://github.com/PrefectHQ/prefect/pull/9138>

### Enhancements

- Add httpx.ConnectTimeout to the list of retry exceptions in base client — <https://github.com/PrefectHQ/prefect/pull/9125>

### Contributors

- @sorendaugaard made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9125>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.10.1...2.10.2>

## Release 2.10.1

Fixes a bug with accessing project recipes through the CLI. See the [pull request](https://github.com/PrefectHQ/prefect/pull/9132) for implementation details.

## Release 2.10.0

Prefect deployments often have critical, implicit dependencies on files and build artifacts, such as containers, that are created and stored outside of Prefect. Each of these dependencies is a potential stumbling block when deploying a flow — you need to ensure that they're satisfied for your flow to run successfully. In this release, we're introducing two new beta features, workers and projects, to help you better manage your flow deployment process. Additionally, we're releasing variables for centralized management of management and expanding events and automations to include blocks. There are a lot of highlighted features this week — but we've also made some significant performance improvements alongside a slew of bug fixes and enhancements!

### Workers [Beta]

Workers are next-generation agents, designed from the ground up to interact with [work pools](https://docs.prefect.io/concepts/work-pools/). Each worker manages flow run infrastructure of a specific type and must pull from a work pool with a matching type. Existing work pools are all "agent" typed for backwards compatibility with our agents — but new work pools can be assigned a specific infrastructure type. Specifying a type for a work pool simplifies choosing what kind of infrastructure will be used when creating a flow run.

Work pools expose rich configuration of their infrastructure. Every work pool type has a base configuration with sensible defaults such that you can begin executing work with just a single command. The infrastructure configuration is fully customizable from the Prefect UI. For example, you can now customize the entire payload used to run flows on Kubernetes — you are not limited to the fields Prefect exposes in its SDK. We provide templating to inject runtime information and common settings into infrastructure creation payloads. Advanced users can add _custom_ template variables which are then exposed the same as Prefect's default options in an easy to use UI.

If the work pool’s configuration is updated, all workers automatically begin using the new settings — you no longer need to redeploy your agents to change infrastructure settings. For advanced use cases, you can override settings on a per-deployment basis.

This release includes Process, Kubernetes, and Docker worker types. Additional worker types will be included in subsequent releases.

Creating a Kubernetes work pool:

<img width="1601" alt="Creating a new Kubernetes work pool" src="https://user-images.githubusercontent.com/2586601/230471683-63875a04-f331-4cf1-8b1b-69c2cd0e4e05.png">
<img width="1601" alt="Advanced configuration of the work pool infrastructure" src="https://user-images.githubusercontent.com/2586601/230471686-7146e930-34fc-43ae-a946-9e3795c4a27a.png">

Adding a new variable to the advanced work pool configuration will expose it in the basic config:

<img width="1551" alt="Adding a variable to the advanced config" src="https://user-images.githubusercontent.com/2586601/230475075-b535b158-62a8-4b88-9439-0054f58e8f77.png">
<img width="1601" alt="New variables can be adjusted in the basic config" src="https://user-images.githubusercontent.com/2586601/230473701-b8db1973-eb03-4682-86cc-64b698356048.png">

See the updated [work pool, workers, & agents concepts documentation](https://docs.prefect.io/latest/concepts/work-pools/) for more information.

### Projects [Beta]

A project is a directory of files that define one or more flows, deployments, Python packages, or any other dependencies that your flow code needs to run. If you’ve been using Prefect, or working on any non-trivial Python project, you probably have an organized structure like this already. Prefect projects are minimally opinionated, so they can work with the structure you already have in place and with the containerization, version control, and build automation tools that you know and love. With projects as directories, you can make relative references between files while retaining portability. We expect most projects to map directly to a git repository. In fact, projects offer a first-class way to clone a git repository so they can be easily shared and synced.

Projects also include a lightweight build system that you can use to define the process for deploying flows in that project. That procedure is specified in a new `prefect.yaml` file, in which you can specify steps to build the necessary artifacts for a project's deployments, push those artifacts, and retrieve them at runtime.

Projects are a contract between you and a worker, specifying what you do when you create a deployment, and what the worker will do before it kicks off that deployment. Together, projects and workers bridge your development environment, where your flow code is written, and your execution environment, where your flow code runs. Create your first Prefect project by following [this tutorial](https://docs.prefect.io/latest/tutorials/projects/).

See the new [project concept doc](https://docs.prefect.io/latest/concepts/projects/) for more information or the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/8930>
- <https://github.com/PrefectHQ/prefect/pull/9103>
- <https://github.com/PrefectHQ/prefect/pull/9105>
- <https://github.com/PrefectHQ/prefect/pull/9112>
- <https://github.com/PrefectHQ/prefect/pull/9093>
- <https://github.com/PrefectHQ/prefect/pull/9083>
- <https://github.com/PrefectHQ/prefect/pull/9041>

### Variables

Variables enable you to store and reuse non-sensitive bits of data, such as configuration information. Variables are named, mutable string values, much like environment variables. They are scoped to a Prefect Server instance or a single workspace in Prefect Cloud. Variables can be created or modified at any time. While variable values are most commonly loaded during flow runtime, they can be loaded in other contexts, at any time, such that they can be used to pass configuration information to Prefect configuration files, such as project steps. You can access any variable via the Python SDK via the `.get()` method.

```python
from prefect import variables

# from a synchronous context
answer = variables.get('the_answer')
print(answer)
# 42

# from an asynchronous context
answer = await variables.get('the_answer')
print(answer)
# 42

# without a default value
answer = variables.get('not_the_answer')
print(answer)
# None

# with a default value
answer = variables.get('not_the_answer', default='42')
print(answer)
# 42
```

See the new [variables concept doc](https://docs.prefect.io/latest/concepts/variables/) for more information or the [pull request](https://github.com/PrefectHQ/prefect/pull/9088) for implementation details.

### Events

Continuing the rollout of events[https://docs.prefect.io/concepts/events-and-resources/] as the primary unit of observability in Prefect Cloud, Prefect will now emit events for all block method calls by default. These events can be viewed in the Event feed, allowing you to analyze the interactions your flows and tasks have with external systems such as storage locations, notification services, and infrastructure. Additionally, you can trigger automations based on these events. For example, you can create an automation that is triggered when a file is uploaded to a storage location.

![image](https://user-images.githubusercontent.com/26799928/230421783-997e4fda-a02f-4bf4-88e1-f51a2f890cf5.png)

### Versioned documentation

We're releasing a lot of new features every week and we know not everyone is on the latest version of Prefect. We've added versioning to our documentation website to make it easier to find the docs for the version of Prefect that you're using.

Now, when you visit the Prefect documentation site, you'll see a version selector at the top of the page.

![versioned docs](https://user-images.githubusercontent.com/228762/230432235-26fc9406-1390-4c63-9956-b8cdabdfba6f.png)

### Breaking Changes

- Unused options for sorting logs have been removed from the API — <https://github.com/PrefectHQ/prefect/pull/7873>

### Enhancements

- Add artifacts view to flow run page — <https://github.com/PrefectHQ/prefect/pull/9109>
- Improve performance of the background event worker — <https://github.com/PrefectHQ/prefect/pull/9019>
- Update deployment flow run creation to default to a SCHEDULED state instead of PENDING — <https://github.com/PrefectHQ/prefect/pull/9049>
- Add `PREFECT_CLIENT_RETRY_EXTRA_CODES` to allow retry on additional HTTP status codes — <https://github.com/PrefectHQ/prefect/pull/9056>
- Improve performance of the background log worker — <https://github.com/PrefectHQ/prefect/pull/9048>
- Update agent cancellation check interval to double the scheduled check interval — <https://github.com/PrefectHQ/prefect/pull/9084>
- Update default agent query interval from 10s to 15s — <https://github.com/PrefectHQ/prefect/pull/9085>
- Add a 10 minute cache to API healthchecks — <https://github.com/PrefectHQ/prefect/pull/9069>
- Improve performance of concurrent task runner — <https://github.com/PrefectHQ/prefect/pull/9073>
- Improve performance of waiting for task submission — <https://github.com/PrefectHQ/prefect/pull/9072>
- Add retry on 502 BAD GATEWAY to client — <https://github.com/PrefectHQ/prefect/pull/9102>
- Update local and remote file systems to return path on write — <https://github.com/PrefectHQ/prefect/pull/8965>
- Add artifacts `/count` route — <https://github.com/PrefectHQ/prefect/pull/9022>
- Improve performance of automatic block registration — <https://github.com/PrefectHQ/prefect/pull/8838>
- Improve performance of log retrieval queries — <https://github.com/PrefectHQ/prefect/pull/9035>
- Improve performance of artifact retrieval — <https://github.com/PrefectHQ/prefect/pull/9061> / <https://github.com/PrefectHQ/prefect/pull/9064>
- Add `--type` option to create work-pool CLI — <https://github.com/PrefectHQ/prefect/pull/8993>
- Improve flow run timeline performance — <https://github.com/PrefectHQ/prefect-ui-library/pull/1315>
- Add flow names to sub flows on the flow run timeline graph — <https://github.com/PrefectHQ/prefect-ui-library/pull/1304>

### Fixes

- Fix bug where iterable defaults were treated as mapped parameters — <https://github.com/PrefectHQ/prefect/pull/9021>
- Fix sequential execution with mapped tasks using the SequentialTaskRunner — <https://github.com/PrefectHQ/prefect/pull/8473>
- Fix race condition where futures did not wait for submission to complete — <https://github.com/PrefectHQ/prefect/pull/9070>
- Fix detection of iterables within `quote` annotations while mapping — <https://github.com/PrefectHQ/prefect/pull/9095>
- Fix Dockerfile copy of UI package files on latest Docker version — <https://github.com/PrefectHQ/prefect/pull/9077>

### Documentation

- Add copy to clipboard button in documentation code blocks — <https://github.com/PrefectHQ/prefect/pull/9026>
- Fixed styling of deployments mermaid diagram — <https://github.com/PrefectHQ/prefect/pull/9017>
- Add documentation for database migrations — <https://github.com/PrefectHQ/prefect/pull/9044>
- Adds documentation for BitBucket to flow code storage types — <https://github.com/PrefectHQ/prefect/pull/9080>
- Update rate limit documentation for Cloud — <https://github.com/PrefectHQ/prefect/pull/9100>

### Contributors

- @mianos made their first contribution in <https://github.com/PrefectHQ/prefect/pull/9077>
- @dominictarro made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8965>
- @joelluijmes
- @john-jam

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.9.0...2.10.0>

## Release 2.9.0

### Track and manage artifacts

Most workflows produce or update an artifact of some kind, whether it's a table, a file, or a model. With Prefect Artifacts, you can track changes to these outputs and richly display them in the UI as tables, markdown, and links. Artifacts may be associated with a particular task run, flow run, or even exist outside a flow run context, enabling you to not only observe your flows, but the objects that they interact with as well.

![Artifacts top-level view](https://user-images.githubusercontent.com/27291717/228905742-0bad7874-6b6b-4000-9111-1c4d0e0bd6e1.png)

A variety of artifact types are available. To create an artifact that produces a table, for example, you can use the `create_table_artifact()` function.

```python
from prefect import task, flow
from prefect.artifacts import create_table_artifact

@task
def my_table_task():
    table_data = [
        {"id": 0, "name": "Dublin", "lat": 53.3498, "lon": -6.2603,},
        {"id": 1, "name": "London", "lat": 51.5074, "lon": -0.1278,},
        {"id": 2, "name": "New York", "lat": 40.7128, "lon": -74.0060,},
        {"id": 3, "name": "Oslo", "lat": 59.9139, "lon": 10.7522,},
        {"id": 4, "name": "Paris", "lat": 48.8566, "lon": 2.3522,},
        {"id": 5, "name": "Rome", "lat": 41.9028, "lon": 12.4964,},
        {"id": 6, "name": "Tokyo", "lat": 35.6895, "lon": 139.6917,},
        {"id": 7, "name": "Vancouver", "lat": 49.2827, "lon": -123.1207,}
    ]

    return create_table_artifact(
        key="cities-table",
        table=table_data,
        description="A table of cities and their coordinates",
    )

@flow
def my_flow():
    table = my_table_task()
    return table

if __name__ == "__main__":
    my_flow()

```

You can view your artifacts in the Artifacts page of the Prefect UI, easily search the data in your new table artifact, and toggle between a rendered and raw version of your data.

![Table artifact in a timeline view](https://user-images.githubusercontent.com/27291717/228905740-bd297de9-6381-45ec-aba3-8b72def70a08.png)

See [the documentation](https://docs.prefect.io/concepts/artifacts) for more information, as well as the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/9003>
- <https://github.com/PrefectHQ/prefect/pull/8832>
- <https://github.com/PrefectHQ/prefect/pull/8932>
- <https://github.com/PrefectHQ/prefect/pull/8875>
- <https://github.com/PrefectHQ/prefect/pull/8874>
- <https://github.com/PrefectHQ/prefect/pull/8985>

### Configure result storage keys

When persisting results, Prefect stores data at a unique, randomly-generated path. While this is convenient for ensuring the result is never overwritten, it limits organization of result files. In this release, we've added configuration of result storage keys, which gives you control over the result file path. Result storage keys can be dynamically formatted with access to all of the modules in `prefect.runtime` and the run's `parameters`.

For example, you can name each result to correspond to the flow run that produced it and a parameter it received:

```python
from prefect import flow, task

@flow()
def my_flow():
    hello_world()
    hello_world(name="foo")
    hello_world(name="bar")

@task(
    persist_result=True,
    result_storage_key="hello__{flow_run.name}__{parameters[name]}.json",
)
def hello_world(name: str = "world"):
    return f"hello {name}"

my_flow()
```

Which will persist three result files in the storage directory:

```
$ ls ~/.prefect/storage | grep "hello__"
hello__rousing-mushroom__bar.json
hello__rousing-mushroom__foo.json
hello__rousing-mushroom__world.json
```

See [the documentation](https://docs.prefect.io/concepts/results/#result-storage-key) for more information.

### Expanded `prefect.runtime`

The `prefect.runtime` module is now the preferred way to access information about the current run. In this release, we've added the following attributes:

- `prefect.runtime.task_run.id`
- `prefect.runtime.task_run.name`
- `prefect.runtime.task_run.task_name`
- `prefect.runtime.task_run.tags`
- `prefect.runtime.task_run.parameters`
- `prefect.runtime.flow_run.name`
- `prefect.runtime.flow_run.flow_name`
- `prefect.runtime.flow_run.parameters`

See [the documentation](https://docs.prefect.io/concepts/runtime-context/) for more information.

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/8947>
- <https://github.com/PrefectHQ/prefect/pull/8948>
- <https://github.com/PrefectHQ/prefect/pull/8949>
- <https://github.com/PrefectHQ/prefect/pull/8951>
- <https://github.com/PrefectHQ/prefect/pull/8954>
- <https://github.com/PrefectHQ/prefect/pull/8956>

### Enhancements

- Add unique integers to worker thread names for inspection — <https://github.com/PrefectHQ/prefect/pull/8908>
- Add support to `JSONSerializer` for serialization of exceptions so they are persisted even on failure — <https://github.com/PrefectHQ/prefect/pull/8922>
- Add Gzip middleware to the UI and API FastAPI apps for compressing responses — <https://github.com/PrefectHQ/prefect/pull/8931>
- Update the runtime to detect flow run information from task run contexts — <https://github.com/PrefectHQ/prefect/pull/8951>

### Fixes

- Fix imports in copytree backport for Python 3.7 — <https://github.com/PrefectHQ/prefect/pull/8925>
- Retry on sqlite operational errors — <https://github.com/PrefectHQ/prefect/pull/8950>
- Add 30 second timeout to shutdown of the log worker thread — <https://github.com/PrefectHQ/prefect/pull/8983>

### Documentation

- Disambiguate reference to "Blocks" — <https://github.com/PrefectHQ/prefect/pull/8921>
- Fix broken concepts link — <https://github.com/PrefectHQ/prefect/pull/8923>
- Add note about fine-grained PAT format — <https://github.com/PrefectHQ/prefect/pull/8929>
- Add `UnpersistedResult` type — <https://github.com/PrefectHQ/prefect/pull/8953>
- Update docs CSS and config for versioning compatibility — <https://github.com/PrefectHQ/prefect/pull/8957>
- Clarify Filesystem package dependencies — <https://github.com/PrefectHQ/prefect/pull/8989>
- Update flow runs documentation — <https://github.com/PrefectHQ/prefect/pull/8919>
- Fix missing backticks on Work Pools concept page — <https://github.com/PrefectHQ/prefect/pull/8942>
- Update links to the release notes in the installation guide — <https://github.com/PrefectHQ/prefect/pull/8974>
- Fix `EXTRA_PIP_PACKAGES` info in Docker guide — <https://github.com/PrefectHQ/prefect/pull/8995>
- Fix `KubernetesJob.job_watch_timeout_seconds` docstring — <https://github.com/PrefectHQ/prefect/pull/8977>
- Add task run runtime to API reference — <https://github.com/PrefectHQ/prefect/pull/8998>
- Add documentation for runtime context — <https://github.com/PrefectHQ/prefect/pull/8999>

### Contributors

- @andreadistefano made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8942>
- @knl made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8974>
- @thomas-te made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8959>

## Release 2.8.7

If you have been watching the experimental section of our release notes, you may have noticed a lot of work around concurrency tooling, flow run graph enhancements, and result artifacts. With this release, these experiments have culminated into exciting features!

### Engine reliability

Supporting mixed asynchronous and synchronous code is complicated, but important. When designing Prefect 2, we wanted to account for the future growth of asynchronous Python and the many user requests for asynchronous task support. Most of this complexity is buried in the Prefect engine, which manages execution of your flows and tasks. With this release, we've made some dramatic improvements to the engine, closing some long-standing bugs and ensuring that it isn't a point of failure when running your flows.

The behavioral changes include:

- All orchestration of flows and tasks happens in a dedicated worker thread
- Synchronous flows are run on the main thread instead of worker threads
    — Solves problems where flow code must be in the main thread e.g. <https://github.com/PrefectHQ/prefect/issues/5991>
- Asynchronous flows no longer share an event loop with the Prefect engine
- Flow timeouts are now enforced with signals
    — Allows interrupt of long-running system calls like `sleep` for more effective timeout enforcement
- Asynchronous flows can be called from sync flows
- Asynchronous tasks can be used as upstream dependencies for sync tasks in async flows
- Synchronous tasks can be submitted from asynchronous flows
- Waiting for many tasks that sleep no longer causes deadlocks
- Flows with thousands of synchronous tasks are less likely to crash
- Debug mode now enables verbose logging from Prefect concurrency internals
- The API limits itself to 100 concurrent requests when using SQLite as a backend
    — Avoids database file contention when using high levels of concurrency
- Resolving task inputs no longer uses worker threads
    — Resolves issues where large numbers of upstream task inputs would cause deadlocks
    — Instead of using worker threads, we wait for upstream tasks on the event loop to support high levels of concurrency

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect/pull/8702>
- <https://github.com/PrefectHQ/prefect/pull/8887>
- <https://github.com/PrefectHQ/prefect/pull/8903>
- <https://github.com/PrefectHQ/prefect/pull/8830>

### Results tab on flow run pages

The Prefect UI now renders information about your flow run and task run results!

This view provides a visual representation of the output of your tasks and flows and, when possible, provides links to results persisted using any of our storage blocks. To see this in your UI, run any flow and navigate to the run page; from there you'll see a new tab, "Results":

![Results list view](https://user-images.githubusercontent.com/27291717/227274576-1379c67c-6624-4a79-9bf7-83ae70e1fb4d.png)
![Results grid view](https://user-images.githubusercontent.com/27291717/227274578-35673508-09e2-4b83-bc22-11538f813eea.png)

See the following pull requests for implementation details:

- <https://github.com/PrefectHQ/prefect-ui-library/pull/1207>
- <https://github.com/PrefectHQ/prefect-ui-library/pull/1213>
- <https://github.com/PrefectHQ/prefect-ui-library/pull/1223>
- <https://github.com/PrefectHQ/prefect/pull/8904>
- <https://github.com/PrefectHQ/prefect/pull/8759>

### Flow run graph

We heard that people loved the simplicity and sleekness of the timeline on the flow run page, but valued the radar graph's ability to traverse between flow runs and subflows runs. This release introduces the ability to expand and collapse subflow runs within the timeline. With these enhancements, the flow run timeline has now evolved into a general purpose flow run graph, with the ability to render thousands of nodes and edges performantly. The radar graph has been retired. You can now observe and explore your flow runs even more quickly and easily in a single flow run graph!

<img width="1497" alt="Flow run timeline" src="https://user-images.githubusercontent.com/2586601/227337664-8d856634-7093-4002-ab55-57986eeaa2ed.png">
<img width="1496" alt="Subflow run expansion" src="https://user-images.githubusercontent.com/2586601/227337673-5cc574c9-76a6-442b-b579-e8fd2a184fd3.png">

### Enhancements

- Add `--reverse` option to the flow run logs CLI to view logs in descending order — <https://github.com/PrefectHQ/prefect/pull/8625>
- Show all flow runs for deployments rather than just the last 7 days — <https://github.com/PrefectHQ/prefect/pull/8837>
- Add jitter to Prefect client request retries — <https://github.com/PrefectHQ/prefect/pull/8839>
- Add `deployment.name` and `deployment.version` to `prefect.runtime` — <https://github.com/PrefectHQ/prefect/pull/8864>
- Add `flow_run.scheduled_start_time` to `prefect.runtime` — <https://github.com/PrefectHQ/prefect/pull/8864>
- Adjust SQLite sync mode for improved performance — <https://github.com/PrefectHQ/prefect/pull/8071>
- Add debug level log of active profile on module import — <https://github.com/PrefectHQ/prefect/pull/8856>
- Update server to use new FastAPI lifespan context manager — <https://github.com/PrefectHQ/prefect/pull/8842>
- Add support for variadic keyword arguments to `Task.map` — <https://github.com/PrefectHQ/prefect/pull/8188>
- Show the full run history in the UI — <https://github.com/PrefectHQ/prefect/pull/8885>

### Fixes

- Fix `prefect dev start` failure — <https://github.com/PrefectHQ/prefect/pull/8850>
- Fix bug where `propose_state` could exceed recursion limits during extended waits — <https://github.com/PrefectHQ/prefect/pull/8827>
- Fix configuration of flow run infrastructure when using agent default — <https://github.com/PrefectHQ/prefect/pull/8872>
- Fix saving block document secrets that have not been modified — <https://github.com/PrefectHQ/prefect/pull/8848>
- Disable SLSA provenance setting in Docker buildx to resolve image pull errors with certain Cloud providers — <https://github.com/PrefectHQ/prefect/pull/8889>
- Fix race condition in worker thread start — <https://github.com/PrefectHQ/prefect/pull/8886>
- The state message has been returned to the flow run metadata panel on the right side of the flow run page — <https://github.com/PrefectHQ/prefect/pull/8885>

### Experimental

- Update to worker base job template logic for nested placeholders — <https://github.com/PrefectHQ/prefect/pull/8795>
- Require lowercase artifact `key` field — <https://github.com/PrefectHQ/prefect/pull/8860>
- Create `emit_event` helper that takes args for an `Event` and emits it via a worker — <https://github.com/PrefectHQ/prefect/pull/8867>
- Allow multiple artifacts to have the same key — <https://github.com/PrefectHQ/prefect/pull/8855>
- Add common values to job configuration prior to flow run submission — <https://github.com/PrefectHQ/prefect/pull/8826>

### Deprecations

- Creating data documents will now throw deprecation warnings — <https://github.com/PrefectHQ/prefect/pull/8760>

### Documentation

- Add documentation for events and resources — <https://github.com/PrefectHQ/prefect/pull/8858>

### Contributors

- @lounis89 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8625>

- @mesejo made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8842>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.6...2.8.7>

## Release 2.8.6

### `prefect.runtime` for context access

Many users of Prefect run their flows in highly dynamic environments; because of this it can be incredibly useful to access information about the current flow run or deployment run outside of a flow function for configuration purposes. For example, if we are running a Prefect deployment within a larger Dask cluster, we might want to use each flow run id as the Dask client name for easier searching of the scheduler logs. Prefect now offers a user-friendly way of accessing this information through the `prefect.runtime` namespace:

```python
from prefect.runtime import flow_run
from prefect import flow
from prefect_dask.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(client_kwargs = {"name": flow_run.id}))
def my_flow():
    ...
```

This will create a Dask client whose name mirrors the flow run ID. Similarly, you can use `prefect.runtime` to access parameters that were passed to this deployment run via `prefect.runtime.deployment.parameters`. Note that all of these attributes will be empty if they are not available.

See <https://github.com/PrefectHQ/prefect/pull/8790> for details.

### Enhancements

- Add deployment id support to `run_deployment` — <https://github.com/PrefectHQ/prefect/pull/7958>
- Disable Postgres JIT for performance improvements — <https://github.com/PrefectHQ/prefect/pull/8804>

### Fixes

- Fix blocking file read in async method `Deployment.load_from_yaml` — <https://github.com/PrefectHQ/prefect/pull/8798>
- Allow tasks and flows to make redundant transitions such as `RUNNING` -> `RUNNING` — <https://github.com/PrefectHQ/prefect/pull/8802>

### Experimental

- Enable setting environment variables for worker submitted flow runs — <https://github.com/PrefectHQ/prefect/pull/8706>
- Add `--work-queue` option to worker CLI — <https://github.com/PrefectHQ/prefect/pull/8771>
- Add artifact description column — <https://github.com/PrefectHQ/prefect/pull/8805>
- Format types in result descriptions as code — <https://github.com/PrefectHQ/prefect/pull/8808>
- Add artifacts for unpersisted results — <https://github.com/PrefectHQ/prefect/pull/8759>
- Update default result descriptions — <https://github.com/PrefectHQ/prefect/pull/8772>

### Documentation

- Update workspace roles table to emphasize differences between roles — <https://github.com/PrefectHQ/prefect/pull/8787>
- Add webhook block docs — <https://github.com/PrefectHQ/prefect/pull/8773>
- Update info on Ray's support for hardware and software — <https://github.com/PrefectHQ/prefect/pull/8811>

### Helm chart

- Helm charts are now automatically published on each Prefect release — <https://github.com/PrefectHQ/prefect/pull/8776>

### Contributors

- @devanshdoshi9

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.5...2.8.6>

## Release 2.8.5

### Enhancements

- Add an endpoint to retrieve data from the collection registry — <https://github.com/PrefectHQ/prefect/pull/8685>
- Remove deployment flow run foreign key to speed up deployment deletion — <https://github.com/PrefectHQ/prefect/pull/8684>

### Fixes

- Fix `prefect cloud login` detection of "ENTER" on some machines — <https://github.com/PrefectHQ/prefect/pull/8705>
- Fix Kubernetes job watch timeout request error by rounding floats — <https://github.com/PrefectHQ/prefect/pull/8733>
- Fix flow load errors by excluding fsspec `2023.3.0` during requirements installation — <https://github.com/PrefectHQ/prefect/pull/8757>
- Fix Deployment and Concurrency Limit pages tabs — <https://github.com/PrefectHQ/prefect/pull/8716>
- Add tests for base exceptions and calls — <https://github.com/PrefectHQ/prefect/pull/8734>

### Experimental

- Refactor supervisor API to allow configuration — <https://github.com/PrefectHQ/prefect/pull/8695>
- Consolidate `WorkItem` and `Call` classes — <https://github.com/PrefectHQ/prefect/pull/8697>
- Use `PREFECT_API_URL` when initializing the events client — <https://github.com/PrefectHQ/prefect/pull/8704>
- Refactor supervisors to interact directly with "Worker" threads — <https://github.com/PrefectHQ/prefect/pull/8714>
- Add chaining to cancel contexts — <https://github.com/PrefectHQ/prefect/pull/8719>
- Add portal abstract base for worker threads and supervisors — <https://github.com/PrefectHQ/prefect/pull/8717>
- Fix bugs in supervisors implementation — <https://github.com/PrefectHQ/prefect/pull/8718>
- Refactor concurrency module and add documentation — <https://github.com/PrefectHQ/prefect/pull/8724>
- Update block event resource IDs to use block-document id instead of name — <https://github.com/PrefectHQ/prefect/pull/8730>
- Add cancellation reporting to calls and waiters — <https://github.com/PrefectHQ/prefect/pull/8731>
- Add worker command output when applying deployments with a work pool — <https://github.com/PrefectHQ/prefect/pull/8725>
- Add support for float timeouts using alarms — <https://github.com/PrefectHQ/prefect/pull/8737>
- Add the ability to discover type from work pool when starting a worker — <https://github.com/PrefectHQ/prefect/pull/8711>
- Add basic event instrumentation to blocks — <https://github.com/PrefectHQ/prefect/pull/8686>

### Documentation

- Corrected typo in Storage.md — <https://github.com/PrefectHQ/prefect/pull/8692>
- Fix `prefect flow-run cancel` help — <https://github.com/PrefectHQ/prefect/pull/8755>

### Contributors

- @Zesky665 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8692>

- @predatorprasad made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8755>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.4...2.8.5>

## Release 2.8.4

### Enhancements

- Enable `DefaultAzureCredential` authentication for Azure filesystem block — <https://github.com/PrefectHQ/prefect/pull/7513>
- Add support for yaml config strings to `KubernetesClusterConfig` — <https://github.com/PrefectHQ/prefect/pull/8643>
- Add `--description` flag to `prefect deployment build` CLI command — <https://github.com/PrefectHQ/prefect/pull/8603>
- Handle SIGTERM received by server gracefully — <https://github.com/PrefectHQ/prefect/pull/7948>
- Optimize database query performance by changing SQLAlchemy lazy loads from `joined` to `selectin` — <https://github.com/PrefectHQ/prefect/pull/8659>
- Add clarifying modal to the task run page in the UI — <https://github.com/PrefectHQ/prefect/pull/8295>

### Fixes

- Ensure flow parameters default values are present during deployment runs — <https://github.com/PrefectHQ/prefect/pull/8666>
- Use a monotonic clock for Kubernetes job watch timeout deadline calculation — <https://github.com/PrefectHQ/prefect/pull/8680>
- Fix version misaligned on the settings page in the UI — <https://github.com/PrefectHQ/prefect/pull/8676>

### Experimental

- Refactor supervisors to manage submission — <https://github.com/PrefectHQ/prefect/pull/8631>
- Improve supervisor repr for debugging — <https://github.com/PrefectHQ/prefect/pull/8633>
- Add timeout support to supervisors — <https://github.com/PrefectHQ/prefect/pull/8649>
- Track flow run id when generating task run results — <https://github.com/PrefectHQ/prefect/pull/8674>
- Create `EventsWorker` to manage client lifecycle and abstract async nature — <https://github.com/PrefectHQ/prefect/pull/8673>

### Documentation

- Add tutorial for running an agent on Azure Container Instances — <https://github.com/PrefectHQ/prefect/pull/8620>
- Add security headers for docs — <https://github.com/PrefectHQ/prefect/pull/8655>
- Add markdown link fix in orchestration docs — <https://github.com/PrefectHQ/prefect/pull/8660>

## New Contributors

- @samdyzon made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7513>

- @mjschock made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8660>
- @jcorrado76 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8603>
- @scharlottej13 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8669>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.3...2.8.4>

## Release 2.8.3

### `on_completion` and `on_failure` hooks for flows and tasks

With this release you can now add client-side hooks that will be called when your flow or task enters a `Completed` or `Failed` state. This is great for any case where you want to execute code without involvement of the Prefect API.

Both flows and tasks include `on_completion` and `on_failure` options where a list of callable hooks can be provided. The callable will receive three arguments:

- `flow`, `flow_run`, and `state` in the case of a flow hook
- `task`, `task_run`, and `state` in the case of a task hook

For example, here we add completion hooks to a flow and a task:

```python
from prefect import task, flow

def my_completion_task_hook_1(task, task_run, state):
    print("This is the first hook — Task completed!!!")

def my_completion_task_hook_2(task, task_run, state):
  print("This is the second hook — Task completed!!!")

def my_completion_flow_hook(flow, flow_run, state):
    print("Flow completed!!!")

@task(on_completion=[my_completion_task_hook_1, my_completion_task_hook_2])
def my_task():
    print("This is the task!")

@flow(on_completion=[my_completion_flow_hook])
def my_flow():
    my_task()

if __name__ == "__main__":
    my_flow()
```

Next, we'll include a failure hook as well. It's worth noting that you can supply both `on_completion` and `on_failure` hooks to a flow or task. Only the hooks that are relevant to the final state of the flow or task will be called.

```python
from prefect import task, flow

def my_task_completion_hook(task, task_run, state):
    print("Our task completed successfully!")

def my_task_failure_hook(task, task_run, state):
    print("Our task failed :(")

@task(on_completion=[my_task_completion_hook], on_failure=[my_task_failure_hook])
def my_task():
    raise Exception("Oh no!")

@flow
def my_flow():
    my_task.submit()

if __name__ == "__main__":
    my_flow()
```

### Enhancements

- Update `quote` handling in input resolution to skip descending into the quoted expression — <https://github.com/PrefectHQ/prefect/pull/8576>
- Add light and dark mode color and contrast enhancements to UI — <https://github.com/PrefectHQ/prefect/pull/8629>

### Fixes

- Fix `Task.map` type hint for type-checker compatibility with async tasks — <https://github.com/PrefectHQ/prefect/pull/8607>
- Update Docker container name sanitization to handle "ce" and "ee" when checking Docker version — <https://github.com/PrefectHQ/prefect/pull/8588>
- Fix Kubernetes Job watch timeout behavior when streaming logs — <https://github.com/PrefectHQ/prefect/pull/8618>
- Fix date range filter selection on the flow runs UI page — <https://github.com/PrefectHQ/prefect/pull/8616>
- Fix Kubernetes not streaming logs when using multiple containers in Job — <https://github.com/PrefectHQ/prefect/pull/8430>

### Experimental

- Update worker variable typing for clearer display in the UI — <https://github.com/PrefectHQ/prefect/pull/8613>
- Update `BaseWorker` to ignore flow runs with associated storage block — <https://github.com/PrefectHQ/prefect/pull/8619>
- Add experimental API for artifacts — <https://github.com/PrefectHQ/prefect/pull/8404>

### Documentation

- Add documentation for resuming a flow run via the UI — <https://github.com/PrefectHQ/prefect/pull/8621>
- Add [`prefect-sifflet`](https://siffletapp.github.io/prefect-sifflet/) to Collections catalog — <https://github.com/PrefectHQ/prefect/pull/8599>

### Contributors

- @jefflaporte made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8430>
- @AzemaBaptiste made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8599>
- @darrida

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.2...2.8.3>

## Release 2.8.2

### Fixes

- Re-enable plugin loading in `prefect` module init — <https://github.com/PrefectHQ/prefect/pull/8569>

### Documentation

- Fix logging format override example — <https://github.com/PrefectHQ/prefect/pull/8565>

### Experimental

- Add events client to `PrefectClient` — <https://github.com/PrefectHQ/prefect/pull/8546>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.1...2.8.2>

## Release 2.8.1

### New names, same behavior

We knew we were onto something big when we [first announced Prefect Orion](https://www.prefect.io/guide/blog/announcing-prefect-orion/), our second-generation orchestration engine, but we didn't know just how big. Orion's foundational design principles of dynamism, developer experience, and observability have shaped the Prefect 2 codebase to such an extent that it's difficult to tell where Orion ends and other components begin. For example, it's been challenging to communicate clearly about the “Orion API” (the orchestration API), an “Orion Server” (a hosted instance of the API and UI), and individual components of that server.

With this release, **we've removed references to "Orion" and replaced them with more explicit, conventional nomenclature throughout the codebase**. All changes are **fully backwards compatible** and will follow our standard deprecation cycle of six months. These changes clarify the function of various components, commands, variables, and more.

See the [deprecated section](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md#deprecated) for a full rundown of changes.

Note: Many settings have been renamed but your old settings will be respected. To automatically convert all of the settings in your current profile to the new names, run the `prefect config validate` command.

### Enhancements

- Add `MattermostWebhook` notification block — <https://github.com/PrefectHQ/prefect/pull/8341>
- Add ability to pass in RRule string to `--rrule` option in `prefect set-schedule` command — <https://github.com/PrefectHQ/prefect/pull/8543>

### Fixes

- Fix default deployment parameters not populating in the UI — <https://github.com/PrefectHQ/prefect/pull/8518>
- Fix ability to use anchor date when setting an interval schedule with the `prefect set-schedule` command — <https://github.com/PrefectHQ/prefect/pull/8524>

### Documentation

- Add table listing available blocks — <https://github.com/PrefectHQ/prefect/pull/8443>
- Fix work pools documentation links — <https://github.com/PrefectHQ/prefect/pull/8477>
- Add examples for custom automation triggers — <https://github.com/PrefectHQ/prefect/pull/8476>
- Add webhooks to Automations  docs — <https://github.com/PrefectHQ/prefect/pull/8514>
- Document Prefect Cloud API rate limits — <https://github.com/PrefectHQ/prefect/pull/8529>

### Experimental

- Add metadata fields to `BaseWorker` — <https://github.com/PrefectHQ/prefect/pull/8527>
- Add default artifact metadata to `LiteralResults` and `PersistedResults` — <https://github.com/PrefectHQ/prefect/pull/8501>

### Deprecated

- Default SQLite database name changed from `orion.db` to `prefect.db`
- Logger `prefect.orion` renamed to `prefect.server`
- Constant `ORION_API_VERSION` renamed to `SERVER_API_VERSION`
- Kubernetes deployment template application name changed from `prefect-orion` to `prefect-server`
- Command `prefect kubernetes manifest orion` renamed to `prefect kubernetes manifest server`
- Log config handler `orion` renamed to `api`
- Class `OrionLogWorker` renamed to `APILogWorker`
- Class `OrionHandler` renamed to `APILogHandler`
- Directory `orion-ui` renamed to `ui`
- Class `OrionRouter` renamed to `PrefectRouter`
- Class `OrionAPIRoute` renamed to `PrefectAPIRoute`
- Class `OrionDBInterface` renamed to `PrefectDBInterface`
- Class `OrionClient` renamed to `PrefectClient`
- Module `prefect.client.orion` renamed to `prefect.client.orchestration`
- Command group `prefect orion` renamed to `prefect server`
- Module `prefect.orion` renamed to `prefect.server`
- The following settings have been renamed:
    — `PREFECT_LOGGING_ORION_ENABLED` → `PREFECT_LOGGING_TO_API_ENABLED`
    — `PREFECT_LOGGING_ORION_BATCH_INTERVAL` → `PREFECT_LOGGING_TO_API_BATCH_INTERVAL`
    — `PREFECT_LOGGING_ORION_BATCH_SIZE` → `PREFECT_LOGGING_TO_API_BATCH_SIZE`
    — `PREFECT_LOGGING_ORION_MAX_LOG_SIZE` → `PREFECT_LOGGING_TO_API_MAX_LOG_SIZE`
    — `PREFECT_LOGGING_ORION_WHEN_MISSING_FLOW` → `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW`
    — `PREFECT_ORION_BLOCKS_REGISTER_ON_START` → `PREFECT_API_BLOCKS_REGISTER_ON_START`
    — `PREFECT_ORION_DATABASE_CONNECTION_URL` → `PREFECT_API_DATABASE_CONNECTION_URL`
    — `PREFECT_ORION_DATABASE_MIGRATE_ON_START` → `PREFECT_API_DATABASE_MIGRATE_ON_START`
    — `PREFECT_ORION_DATABASE_TIMEOUT` → `PREFECT_API_DATABASE_TIMEOUT`
    — `PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT` → `PREFECT_API_DATABASE_CONNECTION_TIMEOUT`
    — `PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS` → `PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS`
    — `PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE`
    — `PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS`
    — `PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS`
    — `PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME`
    — `PREFECT_ORION_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME`
    — `PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE`
    — `PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS`
    — `PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`
    — `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS`
    — `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS`
    — `PREFECT_ORION_API_DEFAULT_LIMIT` → `PREFECT_API_DEFAULT_LIMIT`
    — `PREFECT_ORION_API_HOST` → `PREFECT_SERVER_API_HOST`
    — `PREFECT_ORION_API_PORT` → `PREFECT_SERVER_API_PORT`
    — `PREFECT_ORION_API_KEEPALIVE_TIMEOUT` → `PREFECT_SERVER_API_KEEPALIVE_TIMEOUT`
    — `PREFECT_ORION_UI_ENABLED` → `PREFECT_UI_ENABLED`
    — `PREFECT_ORION_UI_API_URL` → `PREFECT_UI_API_URL`
    — `PREFECT_ORION_ANALYTICS_ENABLED` → `PREFECT_SERVER_ANALYTICS_ENABLED`
    — `PREFECT_ORION_SERVICES_SCHEDULER_ENABLED` → `PREFECT_API_SERVICES_SCHEDULER_ENABLED`
    — `PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED` → `PREFECT_API_SERVICES_LATE_RUNS_ENABLED`
    — `PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED` → `PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED`
    — `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_ENABLED` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED`
    — `PREFECT_ORION_TASK_CACHE_KEY_MAX_LENGTH` → `PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH`
    — `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_ENABLED` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED`

### Contributors

- @qheuristics made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8478>
- @KernelErr made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8485>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.8.0...2.8.1>

## Release 2.8.0

### Prioritize flow runs with work pools 🏊

![Work pools allow you to organize and prioritize work](https://user-images.githubusercontent.com/12350579/217914094-e8064420-294b-4033-b12e-c0f58da521d5.png)

With this release, flow runs can now be prioritized among work queues via work pools! Work pools allow you to organize and prioritize work by grouping related work queues together. Within work pools, you can assign a priority to each queue, and flow runs scheduled on higher priority work queues will be run before flow runs scheduled on lower priority work queues. This allows agents to prioritize work that is more important or time-sensitive even if there is a large backlog of flow runs on other work queues in a given work pool.

All existing work queues will be assigned to a default work pool named `default-agent-pool`. Creating a new work pool can be done via the Work Pools page in the UI or via the CLI.

To create a new work pool named "my-pool" via the CLI:

```bash
prefect work-pool create "my-pool"
```

Each work pool starts out with a default queue. New queues can be added to a work pool via the UI or the CLI.

To create a new work queue in a work pool via the CLI:

```bash
prefect work-queue create "high-priority" --pool "my-pool"
```

Deployments can now be assigned to a work queue in a specific work pool. Use the `--pool` flag to specify the work pool and the `--queue` flag to specify the work queue when building a deployment.

```bash
prefect deployment build \
    --pool my-pool \
    --queue high-priority \
    --name high-priority \
    high_priority_flow.py:high_priority_flow
```

Once a deployment has been created and is scheduling flow runs on a work queue, you can start an agent to pick up those flow runs by starting an agent with the `--pool` flag.

```bash
prefect agent start --pool my-pool
```

Starting an agent with the `--pool` command allows the agent to pick up flow runs for the entire pool even as new queues are added to the pool. If you want to start an agent that only picks up flow runs for a specific queue, you can use the `--queue` flag.

```bash
prefect agent start --pool my-pool --queue high-priority
```

To learn more about work pools, check out the [docs](https://docs.prefect.io/concepts/work-pools/) or see the relevant pull requests:

### Enhancements

- Add ability to filter on work pool and queue when querying flow runs — <https://github.com/PrefectHQ/prefect/pull/8459>
- Ensure agent respects work queue priority — <https://github.com/PrefectHQ/prefect/pull/8458>
- Add ability to create a flow run from the UI with parameters from a previous run — <https://github.com/PrefectHQ/prefect/pull/8405>
- Add generic `Webhook` block — <https://github.com/PrefectHQ/prefect/pull/8401>
- Add override customizations functionality to deployments via CLI — <https://github.com/PrefectHQ/prefect/pull/8349>
- Add ability to reset concurrency limits in CLI to purge existing runs from taking concurrency slots — <https://github.com/PrefectHQ/prefect/pull/8408>
- Ensure matching flow run state information in UI — <https://github.com/PrefectHQ/prefect/pull/8441>
- Customize CLI block registration experience based on `PREFECT_UI_URL` — <https://github.com/PrefectHQ/prefect/pull/8438>

### Fixes

- Fix `prefect dev start` command — <https://github.com/PrefectHQ/prefect/pull/8176>
- Fix display of long log messages when in the UI — <https://github.com/PrefectHQ/prefect/pull/8449>
- Update `get_run_logger` to accommodate returning `logging.LoggerAdapter` — <https://github.com/PrefectHQ/prefect/pull/8422>
- Restore Prefect wrapper around HTTP errors for nicer error messages — <https://github.com/PrefectHQ/prefect/pull/8391>
- Fix display of work pool flow run filter in the UI — <https://github.com/PrefectHQ/prefect/pull/8453>

### Documentation

- Update Infrastructure concept documentation with `extra-pip-package` example and updated `deployment.yaml` — <https://github.com/PrefectHQ/prefect/pull/8465>
- Add work pools documentation — <https://github.com/PrefectHQ/prefect/pull/8377>

### Contributors

- @carderne

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.12...2.8.0>

## Release 2.7.12

### Custom flow and task run names 🎉

Both tasks and flows now expose a mechanism for customizing the names of runs! This new keyword argument (`flow_run_name` for flows, `task_run_name` for tasks) accepts a string that will be used to create a run name for each run of the function. The most basic usage is as follows:

```python
from datetime import datetime
from prefect import flow, task

@task(task_run_name="custom-static-name")
def my_task(name):
  print(f"hi {name}")

@flow(flow_run_name="custom-but-fixed-name")
def my_flow(name: str, date: datetime):
  return my_task(name)

my_flow()
```

This is great, but doesn’t help distinguish between multiple runs of the same task or flow. In order to make these names dynamic, you can template them using the parameter names of the task or flow function, using all of the basic rules of Python string formatting as follows:

```python
from datetime import datetime
from prefect import flow, task

@task(task_run_name="{name}")
def my_task(name):
  print(f"hi {name}")

@flow(flow_run_name="{name}-on-{date:%A}")
def my_flow(name: str, date: datetime):
  return my_task(name)

my_flow()
```

See [the docs](https://docs.prefect.io/tutorials/tasks/#basic-flow-configuration) or <https://github.com/PrefectHQ/prefect/pull/8378> for more details.

### Enhancements

- Update the deployment page to show the runs tab before the description — <https://github.com/PrefectHQ/prefect/pull/8398>

### Fixes

- Fix artifact migration to only include states that have non-null data — <https://github.com/PrefectHQ/prefect/pull/8420>
- Fix error when using `prefect work-queue ls` without enabling work pools — <https://github.com/PrefectHQ/prefect/pull/8427>

### Experimental

- Add error when attempting to apply a deployment to a work pool that hasn't been created yet — <https://github.com/PrefectHQ/prefect/pull/8413>
- Create queues in the correct work pool when applying a deployment for a queue that hasn't been created yet — <https://github.com/PrefectHQ/prefect/pull/8413>

### Contributors

- @NodeJSmith

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.11...2.7.12>

## Release 2.7.11

### Using loggers outside of flows

Prefect now defaults to displaying a warning instead of raising an error when you attempt to use Prefect loggers outside of flow or task runs. We've also added a setting `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW` to allow configuration of this behavior to silence the warning or raise an error as before. This means that you can attach Prefect's logging handler to existing loggers without breaking your workflows.

```python
from prefect import flow
import logging

my_logger = logging.getLogger("my-logger")
my_logger.info("outside the flow")

@flow
def foo():
    my_logger.info("inside the flow")

if __name__ == "__main__":
    foo()
```

We want to see messages from `my-logger` in the UI. We can do this with `PREFECT_LOGGING_EXTRA_LOGGERS`.

```
$ PREFECT_LOGGING_EXTRA_LOGGERS="my-logger" python example.py
example.py:6: UserWarning: Logger 'my-logger' attempted to send logs to Orion without a flow run id. The Orion log handler can only send logs within flow run contexts unless the flow run id is manually provided.
  my_logger.info("outside the flow")
18:09:30.518 | INFO    | my-logger — outside the flow
18:09:31.028 | INFO    | prefect.engine — Created flow run 'elated-curassow' for flow 'foo'
18:09:31.104 | INFO    | my-logger — inside the flow
18:09:31.179 | INFO    | Flow run 'elated-curassow' — Finished in state Completed()
```

Notice, we got a warning. This helps avoid confusion when certain logs don't appear in the UI, but if you understand that you can turn it off:

```
$ prefect config set PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW=ignore
Set 'PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW' to 'ignore'.
Updated profile 'default'.
```

### Enhancements

- Update default task run name to exclude hash of task key — <https://github.com/PrefectHQ/prefect/pull/8292>
- Update Docker images to update preinstalled packages on build — <https://github.com/PrefectHQ/prefect/pull/8288>
- Add PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW to allow loggers to be used outside of flows — <https://github.com/PrefectHQ/prefect/pull/8311>
- Display Runs before Deployments on flow pages — <https://github.com/PrefectHQ/prefect/pull/8386>
- Clarify output CLI message when switching profiles — <https://github.com/PrefectHQ/prefect/pull/8383>

### Fixes

- Fix bug preventing agents from properly updating Cancelling runs to a Cancelled state — <https://github.com/PrefectHQ/prefect/pull/8315>
- Fix bug where Kubernetes job monitoring exited early when no timeout was given — <https://github.com/PrefectHQ/prefect/pull/8350>

### Experimental

- We're working on work pools, groups of work queues. Together, work pools & queues give you greater flexibility and control in organizing and prioritizing work.
     — Add updates to work queue `last_polled` time when polling work pools — <https://github.com/PrefectHQ/prefect/pull/8338>
     — Add CLI support for work pools — <https://github.com/PrefectHQ/prefect/pull/8259>
     — Add fields to `work_queue` table to accommodate work pools — <https://github.com/PrefectHQ/prefect/pull/8264>
     — Add work queue data migration — <https://github.com/PrefectHQ/prefect/pull/8327>
     — Fix default value for priority on `WorkQueue` core schema — <https://github.com/PrefectHQ/prefect/pull/8373>
- Add ability to exclude experimental fields in API calls — <https://github.com/PrefectHQ/prefect/pull/8274>, <https://github.com/PrefectHQ/prefect/pull/8331>
- Add Prefect Cloud Events schema and clients — <https://github.com/PrefectHQ/prefect/pull/8357>

### Documentation

- Add git commands to Prefect Recipes contribution page — <https://github.com/PrefectHQ/prefect/pull/8283>
- Add `retry_delay_seconds` and `exponential_backoff` examples to Tasks retries documentation — <https://github.com/PrefectHQ/prefect/pull/8280>
- Add role permissions regarding block secrets — <https://github.com/PrefectHQ/prefect/pull/8309>
- Add getting started tutorial video to Prefect Cloud Quickstart — <https://github.com/PrefectHQ/prefect/pull/8336>
- Add tips for re-registering blocks from Prefect Collections — <https://github.com/PrefectHQ/prefect/pull/8333>
- Improve examples for Kubernetes infrastructure overrides — <https://github.com/PrefectHQ/prefect/pull/8312>
- Add mention of reverse proxy for `PREFECT_API_URL` config — <https://github.com/PrefectHQ/prefect/pull/8240>
- Fix unused Cloud Getting Started page — <https://github.com/PrefectHQ/prefect/pull/8291>
- Fix Prefect Cloud typo in FAQ — <https://github.com/PrefectHQ/prefect/pull/8317>

### Collections

- Add `ShellOperation` implementing `JobBlock` in `v0.1.4` release of `prefect-shell` — <https://github.com/PrefectHQ/prefect-shell/pull/55>
- Add `CensusSync` implementing `JobBlock` in `v0.1.1` release of `prefect-census` — <https://github.com/PrefectHQ/prefect-census/pull/15>

### Contributors

- @chiaberry
- @hozn
- @manic-miner
- @space-age-pete

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.10...2.7.11>

## Release 2.7.10

### Flow run cancellation enhancements

We're excited to announce an upgrade to our flow run cancellation feature, resolving common issues.

We added SIGTERM handling to the flow run engine. When cancellation is requested, the agent sends a termination signal to the flow run infrastructure. Previously, this signal resulted in the immediate exit of the flow run. Now, the flow run will detect the signal and attempt to shut down gracefully. This gives the run an opportunity to clean up any resources it is managing. If the flow run does not gracefully exit in a reasonable time (this differs per infrastructure type), it will be killed.

We improved our handling of runs that are in the process of cancelling. When a run is cancelled, it's first placed in a "cancelling" state then moved to a "cancelled" state when cancellation is complete. Previously, concurrency slots were released as soon as cancellation was requested. Now, the flow run will continue to occupy concurrency slots until a "cancelled" state is reached.

We added cleanup of tasks and subflows belonging to cancelled flow runs. Previously, these tasks and subflows could be left in a "running" state. This can cause problems with concurrency slot consumption and restarts, so we've added a service that updates the states of the children of recently cancelled flow runs.

See <https://github.com/PrefectHQ/prefect/pull/8126> for implementation details.

### Multiarchitecture Docker builds

In 2.7.8, we announced that we were publishing development Docker images, including multiarchitecture images. This was the first step in the incremental rollout of multiarchitecture Docker images. We're excited to announce we will be publishing multiarchitecture Docker images starting with this release.

You can try one of the new images by including the `--platform` specifier, e.g.:

```bash
docker run --platform linux/arm64 --pull always prefecthq/prefect:2-latest prefect version
```

We will be publishing images for the following architectures:

- linux/amd64
- linux/arm64

This should provide a significant speedup to anyone running containers on ARM64 machines (I'm looking at you, Apple M1 chips!) and reduce the complexity for our users that are deploying on different platforms. The workflow for building our images was rewritten from scratch, and it'll be easy for us to expand support to include other common platforms.

Shoutout to [@ddelange](https://github.com/ddelange) who led implementation of the feature.
See <https://github.com/PrefectHQ/prefect/pull/7902> for details.

### Enhancements

- Add [`is_schedule_active` option](https://docs.prefect.io/api-ref/prefect/deployments/#prefect.deployments.Deployment) to `Deployment` class to allow control of automatic scheduling — <https://github.com/PrefectHQ/prefect/pull/7430>

- Add documentation links to blocks in UI — <https://github.com/PrefectHQ/prefect/pull/8210>
- Add Kubernetes kube-system permissions to Prefect agent template for retrieving UUID from kube-system namespace — <https://github.com/PrefectHQ/prefect/pull/8205>
- Add support for obscuring secrets in nested block fields in the UI — <https://github.com/PrefectHQ/prefect/pull/8246>
- Enable publish of multiarchitecture Docker builds on release — <https://github.com/PrefectHQ/prefect/pull/7902>
- Add `CANCELLING` state type — <https://github.com/PrefectHQ/prefect/pull/7794>
- Add graceful shutdown of engine on `SIGTERM` — <https://github.com/PrefectHQ/prefect/pull/7887>
- Add cancellation cleanup service — <https://github.com/PrefectHQ/prefect/pull/8093>
- Add `PREFECT_ORION_API_KEEPALIVE_TIMEOUT` setting to allow configuration of Uvicorn `timeout-keep-alive` setting — <https://github.com/PrefectHQ/prefect/pull/8190>

### Fixes

- Fix server compatibility with clients on 2.7.8 — <https://github.com/PrefectHQ/prefect/pull/8272>
- Fix tracking of long-running Kubernetes jobs and add handling for connection failures — <https://github.com/PrefectHQ/prefect/pull/8189>

### Experimental

- Add functionality to specify a work pool when starting an agent — <https://github.com/PrefectHQ/prefect/pull/8222>
- Disable `Work Queues` tab view when work pools are enabled — <https://github.com/PrefectHQ/prefect/pull/8257>
- Fix property for `WorkersTable` in UI — <https://github.com/PrefectHQ/prefect/pull/8232>

### Documentation

- [Add Prefect Cloud Quickstart tutorial](https://docs.prefect.io/ui/cloud-getting-started/) — <https://github.com/PrefectHQ/prefect/pull/8227>
- Add `project_urls` to `setup.py` — <https://github.com/PrefectHQ/prefect/pull/8224>
- Add configuration to `mkdocs.yml` to enable versioning at a future time — <https://github.com/PrefectHQ/prefect/pull/8204>
- Improve [contributing documentation](https://docs.prefect.io/contributing/overview/) with venv instructions — <https://github.com/PrefectHQ/prefect/pull/8247>
- Update documentation on [KubernetesJob options](https://docs.prefect.io/concepts/infrastructure/#kubernetesjob) — <https://github.com/PrefectHQ/prefect/pull/8261>
- Update documentation on [workspace-level roles](https://docs.prefect.io/ui/roles/#workspace-level-roles) — <https://github.com/PrefectHQ/prefect/pull/8263>

### Collections

- Add [prefect-openai](https://prefecthq.github.io/prefect-openai/) to [Collections catalog](https://docs.prefect.io/collections/catalog/) — <https://github.com/PrefectHQ/prefect/pull/8236>

### Contributors

- @ddelange
- @imsurat
- @Laerte

## Release 2.7.9

### Enhancements

- Add `--head` flag to `flow-run logs` CLI command to limit the number of logs returned — <https://github.com/PrefectHQ/prefect/pull/8003>
- Add `--num_logs` option to `flow-run logs` CLI command to specify the number of logs returned — <https://github.com/PrefectHQ/prefect/pull/8003>
- Add option to filter out `.git` files when reading files with the GitHub storage block — <https://github.com/PrefectHQ/prefect/pull/8193>

### Fixes

- Fix bug causing failures when spawning Windows subprocesses — <https://github.com/PrefectHQ/prefect/pull/8184>
- Fix possible recursive loop when blocks label themselves as both their own parent and reference — <https://github.com/PrefectHQ/prefect/pull/8197>

### Documentation

- Add [recipe contribution page](https://docs.prefect.io/recipes/recipes/#contributing-recipes) and [AWS Chalice](https://docs.prefect.io/recipes/recipes/#recipe-catalog) recipe — <https://github.com/PrefectHQ/prefect/pull/8183>
- Add new `discourse` and `blog` admonition types — <https://github.com/PrefectHQ/prefect/pull/8202>
- Update Automations and Notifications documentation — <https://github.com/PrefectHQ/prefect/pull/8140>
- Fix minor API docstring formatting issues — <https://github.com/PrefectHQ/prefect/pull/8196>

### Collections

- [`prefect-openai` 0.1.0](https://github.com/PrefectHQ/prefect-openai) newly released with support for authentication and completions

### Experimental

- Add ability for deployment create and deployment update to create work pool queues — <https://github.com/PrefectHQ/prefect/pull/8129>

## New Contributors

- @mj0nez made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8201>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.8...2.7.9>

## Release 2.7.8

### Flow run timeline view

We're excited to announce that a new timeline graph has been added to the flow run page.
This view helps visualize how execution of your flow run takes place in time, an alternative to the radar view that focuses on the structure of dependencies between task runs.

This feature is currently in beta and we have lots of improvements planned in the near future! We're looking forward to your feedback.

![The timeline view visualizes execution of your flow run over time](https://user-images.githubusercontent.com/6200442/212138540-78586356-89bc-4401-a700-b80b15a17020.png)

### Enhancements

- Add [task option `refresh_cache`](https://docs.prefect.io/concepts/tasks/#refreshing-the-cache) to update the cached data for a task run — <https://github.com/PrefectHQ/prefect/pull/7856>
- Add logs when a task run receives an abort signal and is in a non-final state — <https://github.com/PrefectHQ/prefect/pull/8097>
- Add [publishing of multiarchitecture Docker images](https://hub.docker.com/r/prefecthq/prefect-dev) for development builds  — <https://github.com/PrefectHQ/prefect/pull/7900>
- Add `httpx.WriteError` to client retryable exceptions — <https://github.com/PrefectHQ/prefect/pull/8145>
- Add support for memory limits and privileged containers to `DockerContainer` — <https://github.com/PrefectHQ/prefect/pull/8033>

### Fixes

- Add support for `allow_failure` to mapped task arguments — <https://github.com/PrefectHQ/prefect/pull/8135>
- Update conda requirement regex to support channel and build hashes — <https://github.com/PrefectHQ/prefect/pull/8137>
- Add numpy array support to orjson serialization — <https://github.com/PrefectHQ/prefect/pull/7912>

### Experimental

- Rename "Worker pools" to "Work pools" — <https://github.com/PrefectHQ/prefect/pull/8107>
- Rename default work pool queue — <https://github.com/PrefectHQ/prefect/pull/8117>
- Add worker configuration — <https://github.com/PrefectHQ/prefect/pull/8100>
- Add `BaseWorker` and `ProcessWorker` — <https://github.com/PrefectHQ/prefect/pull/7996>

### Documentation

- Add YouTube video to welcome page — <https://github.com/PrefectHQ/prefect/pull/8090>
- Add social links — <https://github.com/PrefectHQ/prefect/pull/8088>
- Increase visibility of Prefect Cloud and Orion REST API documentation — <https://github.com/PrefectHQ/prefect/pull/8134>

## New Contributors

- @muddi900 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8101>

- @ddelange made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7900>
- @toro-berlin made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7856>
- @Ewande made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7912>
- @brandonreid made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8153>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.7...2.7.8>

## Release 2.7.7

### Improved reference documentation

The API reference documentation has been completely rehauled with improved navigation and samples.

The best place to view the REST API documentation is on [Prefect Cloud](https://app.prefect.cloud/api/docs).

<img width="1659" alt="Cloud API Reference Documentation" src="https://user-images.githubusercontent.com/2586601/211107172-cbded5a4-e50c-452f-8525-e36b5988f82e.png">

Note: you can also view the REST API documentation [embedded in our open source documentation](https://docs.prefect.io/api-ref/rest-api-reference/).

We've also improved the parsing and rendering of reference documentation for our Python API. See the [@flow decorator reference](https://docs.prefect.io/api-ref/prefect/flows/#prefect.flows.flow) for example.

### Enhancements

- Add link to blocks catalog after registering blocks in CLI — <https://github.com/PrefectHQ/prefect/pull/8017>
- Add schema migration of block documents during `Block.save` — <https://github.com/PrefectHQ/prefect/pull/8056>
- Update result factory creation to avoid creating an extra client instance — <https://github.com/PrefectHQ/prefect/pull/8072>
- Add logs for deployment flow code loading — <https://github.com/PrefectHQ/prefect/pull/8075>
- Update `visit_collection` to support annotations e.g. `allow_failure` — <https://github.com/PrefectHQ/prefect/pull/7263>
- Update annotations to inherit from `namedtuple` for serialization support in Dask — <https://github.com/PrefectHQ/prefect/pull/8037>
- Add `PREFECT_API_TLS_INSECURE_SKIP_VERIFY` setting to disable client SSL verification — <https://github.com/PrefectHQ/prefect/pull/7850>
- Update OpenAPI schema for flow parameters to include positions for display — <https://github.com/PrefectHQ/prefect/pull/8013>
- Add parsing of flow docstrings to populate parameter descriptions in the OpenAPI schema — <https://github.com/PrefectHQ/prefect/pull/8004>
- Add `validate` to `Block.load` allowing validation to be disabled — <https://github.com/PrefectHQ/prefect/pull/7862>
- Improve error message when saving a block with an invalid name — <https://github.com/PrefectHQ/prefect/pull/8038>
- Add limit to task run cache key size — <https://github.com/PrefectHQ/prefect/pull/7275>
- Add limit to RRule length — <https://github.com/PrefectHQ/prefect/pull/7762>
- Add flow run history inside the date range picker — <https://github.com/PrefectHQ/orion-design/issues/994>

### Fixes

- Fix bug where flow timeouts started before waiting for upstreams — <https://github.com/PrefectHQ/prefect/pull/7993>
- Fix captured Kubernetes error type in `get_job` — <https://github.com/PrefectHQ/prefect/pull/8018>
- Fix `prefect cloud login` error when no workspaces exist — <https://github.com/PrefectHQ/prefect/pull/8034>
- Fix serialization of `SecretDict` when used in deployments — <https://github.com/PrefectHQ/prefect/pull/8074>
- Fix bug where `visit_collection` could fail when accessing extra Pydantic fields — <https://github.com/PrefectHQ/prefect/pull/8083>

### Experimental

- Add pages and routers for workers — <https://github.com/PrefectHQ/prefect/pull/7973>

### Documentation

- Update API reference documentation to use new parser and renderer — <https://github.com/PrefectHQ/prefect/pull/7855>
- Add new REST API reference using Redoc — <https://github.com/PrefectHQ/prefect/pull/7503>

### Collections

- [`prefect-aws` 0.2.2](https://github.com/PrefectHQ/prefect-aws/releases/tag/v0.2.2) released with many improvements to `S3Bucket`

### Contributors

- @j-tr made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8013>

- @toby-coleman made their first contribution in <https://github.com/PrefectHQ/prefect/pull/8083>
- @riquelmev made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7768>
- @joelluijmes

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.5...2.7.7>

## Release 2.7.6

This release fixes a critical bug in the SQLite database migrations in 2.7.4 and 2.7.5.

See <https://github.com/PrefectHQ/prefect/issues/8058> for details.

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.5...2.7.6>

## Release 2.7.5

### Schedule flow runs and read logs from the CLI

You can now specify either `--start-in` or `--start-at` when running deployments from the CLI.

```
❯ prefect deployment run foo/test --start-at "3pm tomorrow"
Creating flow run for deployment 'foo/test'...
Created flow run 'pompous-porpoise'.
└── UUID: 0ce7930e-8ec0-40cb-8a0e-65bccb7a9605
└── Parameters: {}
└── Scheduled start time: 2022-12-06 15:00:00
└── URL: <no dashboard available>
```

You can also get the logs for a flow run using `prefect flow-run logs <flow run UUID>`

```
❯ prefect flow-run logs 7aec7a60-a0ab-4f3e-9f2a-479cd85a2aaf
2022-12-29 20:00:40.651 | INFO    | Flow run 'optimal-pegasus' — meow
2022-12-29 20:00:40.652 | INFO    | Flow run 'optimal-pegasus' — that food in my bowl is gross
2022-12-29 20:00:40.652 | WARNING | Flow run 'optimal-pegasus' — seriously, it needs to be replaced ASAP
2022-12-29 20:00:40.662 | INFO    | Flow run 'optimal-pegasus' — Finished in state Completed()
```

### Enhancements

- Add `--start-in` and `--start-at` to `prefect deployment run` — <https://github.com/PrefectHQ/prefect/pull/7772>
- Add `flow-run logs` to get logs using the CLI — <https://github.com/PrefectHQ/prefect/pull/7982>

### Documentation

- Fix task annotation in task runner docs — <https://github.com/PrefectHQ/prefect/pull/7977>
- Add instructions for building custom blocks — <https://github.com/PrefectHQ/prefect/pull/7979>

### Collections

- Added `BigQueryWarehouse` block in `prefect-gcp` v0.2.1
- Added `AirbyteConnection` block in `prefect-airbyte` v0.2.0
- Added dbt Cloud metadata API client to `DbtCloudCredentials` in `prefect-dbt` v0.2.7

### Experimental

- Fix read worker pool queue endpoint — <https://github.com/PrefectHQ/prefect/pull/7995>
- Fix error in worker pool queue endpoint — <https://github.com/PrefectHQ/prefect/pull/7997>
- Add filtering to flow runs by worker pool and worker pool queue attributes — <https://github.com/PrefectHQ/prefect/pull/8006>

### Contributors

- @ohadch made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7982>

- @mohitsaxenaknoldus made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7980>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.4...2.7.5>

## Release 2.7.4

### Improvements to retry delays: multiple delays, exponential backoff, and jitter

When configuring task retries, you can now configure a delay for each retry! The `retry_delay_seconds` option accepts a list of delays for custom retry behavior. For example, the following task will wait for successively increasing intervals before the next attempt starts:

```python
from prefect import task, flow
import random

@task(retries=3, retry_delay_seconds=[1, 10, 100])
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

Additionally, you can pass a callable that accepts the number of retries as an argument and returns a list. Prefect includes an `exponential_backoff` utility that will automatically generate a list of retry delays that correspond to an exponential backoff retry strategy. The following flow will wait for 10, 20, then 40 seconds before each retry.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff
import random

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=10))
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

Many users that configure exponential backoff also wish to jitter the delay times to prevent "thundering herd" scenarios, where many tasks all retry at exactly the same time, causing cascading failures. The `retry_jitter_factor` option can be used to add variance to the base delay. For example, a retry delay of `10` seconds with a `retry_jitter_factor` of `0.5` will be allowed to delay up to `15` seconds. Large values of `retry_jitter_factor` provide more protection against "thundering herds", while keeping the average retry delay time constant. For example, the following task adds jitter to its exponential backoff so the retry delays will vary up to a maximum delay time of 20, 40, and 80 seconds respectively.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff
import random

@task(
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    retry_jitter_factor=1,
)
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

See <https://github.com/PrefectHQ/prefect/pull/7961> for implementation details.

### Enhancements

- Add task run names to the `/graph`  API route — <https://github.com/PrefectHQ/prefect/pull/7951>
- Add vcs directories `.git` and `.hg` (mercurial) to default `.prefectignore` — <https://github.com/PrefectHQ/prefect/pull/7919>
- Increase the default thread limit from 40 to 250 — <https://github.com/PrefectHQ/prefect/pull/7961>

### Deprecations

- Add removal date to tag-based work queue deprecation messages — <https://github.com/PrefectHQ/prefect/pull/7930>

### Documentation

- Fix `prefect deployment` command listing — <https://github.com/PrefectHQ/prefect/pull/7949>
- Add workspace transfer documentation — <https://github.com/PrefectHQ/prefect/pull/7941>
- Fix docstring examples in `PrefectFuture` — <https://github.com/PrefectHQ/prefect/pull/7877>
- Update `setup.py` metadata to link to correct repo — <https://github.com/PrefectHQ/prefect/pull/7933>

### Experimental

- Add experimental workers API routes — <https://github.com/PrefectHQ/prefect/pull/7896>

### Collections

- New [`prefect-google-sheets` collection](https://stefanocascavilla.github.io/prefect-google-sheets/)

### Contributors

- @devanshdoshi9 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7949>

- @stefanocascavilla made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7960>
- @quassy made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7919>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.3...2.7.4>

## Release 2.7.3

### Fixes

- Fix bug where flows with names that do not match the function name could not be loaded — <https://github.com/PrefectHQ/prefect/pull/7920>
- Fix type annotation for `KubernetesJob.job_watch_timeout_seconds` — <https://github.com/PrefectHQ/prefect/pull/7914>
- Keep data from being lost when assigning a generator to `State.data` — <https://github.com/PrefectHQ/prefect/pull/7714>

## Release 2.7.2

### Rescheduling paused flow runs

When pausing a flow run, you can ask that Prefect reschedule the run for you instead of blocking until resume. This allows infrastructure to tear down, saving costs if the flow run is going to be pasued for significant amount of time.

You can request that a flow run be rescheduled by setting the `reschedule` option when calling `pause_flow_run`.

```python
from prefect import task, flow, pause_flow_run

@task(persist_result=True)
async def marvin_setup():
    return "a raft of ducks walk into a bar..."

@task(persist_result=True)
async def marvin_punchline():
    return "it's a wonder none of them ducked!"

@flow(persist_result=True)
async def inspiring_joke():
    await marvin_setup()
    await pause_flow_run(timeout=600, reschedule=True)  # pauses for 10 minutes
    await marvin_punchline()
```

If set up as a deployment, running this flow will set up a joke, then pause and leave execution until it is resumed. Once resumed either with the `resume_flow_run` utility or the Prefect UI, the flow will be rescheduled and deliver the punchline.

In order to use this feature pauses, the flow run must be associated with a deployment and results must be enabled.

Read the [pause documentation](https://docs.prefect.io/concepts/flows/#pause-a-flow-run) or see the [pull request](https://github.com/PrefectHQ/prefect/pull/7738) for details.

### Pausing flow runs from the outside

Flow runs from deployments can now be paused outside of the flow itself!

The UI features a **Pause** button for flow runs that will stop execution at the beginning of the _next_ task that runs. Any currently running tasks will be allowed to complete. Resuming this flow will schedule it to start again.

You can also pause a flow run from code: the `pause_flow_run` utility now accepts an optional `flow_run_id` argument. For example, you can pause a flow run from another flow run!

Read the [pause documentation](https://docs.prefect.io/concepts/flows/#pause-a-flow-run) or see the [pull request](https://github.com/PrefectHQ/prefect/pull/7863) for details.

### Pages for individual task run concurrency limits

When viewing task run concurrency in the UI, each limit has its own page. Included in the details for each limit is the tasks that are actively part of that limit.

<img width="1245" alt="image" src="https://user-images.githubusercontent.com/6200442/207954852-60e7a185-0f9d-4a3d-b9f7-2b393ef12726.png">

### Enhancements

- Improve Prefect import time by deferring imports — <https://github.com/PrefectHQ/prefect/pull/7836>
- Add Opsgenie notification block — <https://github.com/PrefectHQ/prefect/pull/7778>
- Add individual concurrency limit page with active runs list — <https://github.com/PrefectHQ/prefect/pull/7848>
- Add `PREFECT_KUBERNETES_CLUSTER_UID` to allow bypass of `kube-system` namespace read — <https://github.com/PrefectHQ/prefect/pull/7864>
- Refactor `pause_flow_run` for consistency with engine state handling — <https://github.com/PrefectHQ/prefect/pull/7857>
- API: Allow `reject_transition` to return current state — <https://github.com/PrefectHQ/prefect/pull/7830>
- Add `SecretDict` block field that obfuscates nested values in a dictionary — <https://github.com/PrefectHQ/prefect/pull/7885>

### Fixes

- Fix bug where agent concurrency slots may not be released — <https://github.com/PrefectHQ/prefect/pull/7845>
- Fix circular imports in the `orchestration` module — <https://github.com/PrefectHQ/prefect/pull/7883>
- Fix deployment builds with scripts that contain flow calls — <https://github.com/PrefectHQ/prefect/pull/7817>
- Fix path argument behavior in `LocalFileSystem` block — <https://github.com/PrefectHQ/prefect/pull/7891>
- Fix flow cancellation in `Process` block on Windows — <https://github.com/PrefectHQ/prefect/pull/7799>

### Documentation

- Add documentation for Automations UI — <https://github.com/PrefectHQ/prefect/pull/7833>
- Mention recipes and tutorials under Recipes and Collections pages — <https://github.com/PrefectHQ/prefect/pull/7876>
- Add documentation for Task Run Concurrency UI — <https://github.com/PrefectHQ/prefect/pull/7840>
- Add `with_options` example to collections usage docs — <https://github.com/PrefectHQ/prefect/pull/7894>
- Add a link to orion design and better title to UI readme — <https://github.com/PrefectHQ/prefect/pull/7484>

### Collections

- New [`prefect-kubernetes`](https://prefecthq.github.io/prefect-kubernetes/) collection for [Kubernetes](https://kubernetes.io/) — <https://github.com/PrefectHQ/prefect/pull/7907>
- New [`prefect-bitbucket`](https://prefecthq.github.io/prefect-bitbucket/) collection for [Bitbucket](https://bitbucket.org/product) — <https://github.com/PrefectHQ/prefect/pull/7907>

## Contributors

- @jlutran

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.7.1...2.7.2>

## Release 2.7.1

### Task concurrency limits page

You can now add task concurrency limits in the ui!

![image](https://user-images.githubusercontent.com/6200442/206586749-3f9fff36-5359-41a9-8727-60523cf89071.png)

### Enhancements

- Add extra entrypoints setting for user module injection; allows registration of custom blocks — <https://github.com/PrefectHQ/prefect/pull/7179>
- Update orchestration rule to wait for scheduled time to only apply to transition to running — <https://github.com/PrefectHQ/prefect/pull/7585>
- Use cluster UID and namespace instead of cluster "name" for `KubernetesJob` identifiers — <https://github.com/PrefectHQ/prefect/pull/7747>
- Add a task run concurrency limits page — <https://github.com/PrefectHQ/prefect/pull/7779>
- Add setting to toggle interpreting square brackets as style — <https://github.com/PrefectHQ/prefect/pull/7810>
- Move `/health` API route to root router — <https://github.com/PrefectHQ/prefect/pull/7765>
- Add `PREFECT_API_ENABLE_HTTP2` setting to allow HTTP/2 to be disabled — <https://github.com/PrefectHQ/prefect/pull/7802>
- Monitor process after kill and return early when possible — <https://github.com/PrefectHQ/prefect/pull/7746>
- Update `KubernetesJob` to watch jobs without timeout by default — <https://github.com/PrefectHQ/prefect/pull/7786>
- Bulk deletion of flows, deployments, and work queues from the UI — <https://github.com/PrefectHQ/prefect/pull/7824>

### Fixes

- Add lock to ensure that alembic commands are not run concurrently — <https://github.com/PrefectHQ/prefect/pull/7789>
- Release task concurrency slots when transition is rejected as long as the task is not in a running state — <https://github.com/PrefectHQ/prefect/pull/7798>
- Fix issue with improperly parsed flow run notification URLs — <https://github.com/PrefectHQ/prefect/pull/7173>
- Fix radar not updating without refreshing the page — <https://github.com/PrefectHQ/prefect/pull/7824>
- UI: Fullscreen layouts on screens < `lg` should take up all the available space — <https://github.com/PrefectHQ/prefect/pull/7792>

### Documentation

- Add documentation for creating a flow run from deployments — <https://github.com/PrefectHQ/prefect/pull/7696>
- Move `wait_for` examples to the tasks documentation — <https://github.com/PrefectHQ/prefect/pull/7788>

## Contributors

- @t-yuki made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7741>

- @padbk made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7173>

## Release 2.7.0

### Flow run cancellation

We're excited to announce a new flow run cancellation feature!

Flow runs can be cancelled from the CLI, UI, REST API, or Python client.

For example:

```
prefect flow-run cancel <flow-run-id>
```

When cancellation is requested, the flow run is moved to a "Cancelling" state. The agent monitors the state of flow runs and detects that cancellation has been requested. The agent then sends a signal to the flow run infrastructure, requesting termination of the run. If the run does not terminate after a grace period (default of 30 seconds), the infrastructure will be killed, ensuring the flow run exits.

Unlike the implementation of cancellation in Prefect 1 — which could fail if the flow run was stuck — this provides a strong guarantee of cancellation.

Note: this process is robust to agent restarts, but does require that an agent is running to enforce cancellation.

Support for cancellation has been added to all core library infrastructure types:

- Docker Containers (<https://github.com/PrefectHQ/prefect/pull/7684>)
- Kubernetes Jobs (<https://github.com/PrefectHQ/prefect/pull/7701>)
- Processes (<https://github.com/PrefectHQ/prefect/pull/7635>)

Cancellation support is in progress for all collection infrastructure types:

- ECS Tasks (<https://github.com/PrefectHQ/prefect-aws/pull/163>)
- Google Cloud Run Jobs (<https://github.com/PrefectHQ/prefect-gcp/pull/76>)
- Azure Container Instances (<https://github.com/PrefectHQ/prefect-azure/pull/58>)

At this time, this feature requires the flow run to be submitted by an agent — flow runs without deployments cannot be cancelled yet, but that feature is [coming soon](https://github.com/PrefectHQ/prefect/pull/7150).

See <https://github.com/PrefectHQ/prefect/pull/7637> for more details

### Flow run pause and resume

In addition to cancellations, flow runs can also be paused for manual approval!

```python
from prefect import flow, pause_flow_run


@flow
def my_flow():
    print("hi!")
    pause_flow_run()
    print("bye!")
```

A new `pause_flow_run` utility is provided — when called from within a flow, the flow run is moved to a "Paused" state and execution will block. Any tasks that have begun execution before pausing will finish. Infrastructure will keep running, polling to check whether the flow run has been resumed. Paused flow runs can be resumed with the `resume_flow_run` utility, or from the UI.

A timeout can be supplied to the `pause_flow_run` utility — if the flow run is not resumed within the specified timeout, the flow will fail.

This blocking style of pause that keeps infrastructure running is supported for all flow runs, including subflow runs.

See <https://github.com/PrefectHQ/prefect/pull/7637> for more details.

### Logging of prints in flows and tasks

Flows or tasks can now opt-in to logging print statements. This is much like the `log_stdout` feature in Prefect 1, but we've improved the _scoping_ so you can enable or disable the feature at the flow or task level.

In the following example, the print statements will be redirected to the logger for the flow run and task run accordingly:

```python
from prefect import task, flow

@task
def my_task():
    print("world")

@flow(log_prints=True)
def my_flow():
    print("hello")
    my_task()
```

The output from these prints will appear in the UI!

This feature will also capture prints made in functions called by tasks or flows — as long as you're within the context of the run the prints will be logged.

If you have a sensitive task, it can opt-out even if the flow has enabled logging of prints:

```python
@task(log_prints=False)
def my_secret_task():
    print(":)")
```

This print statement will appear locally as normal, but won't be sent to the Prefect logger or API.

See [the logging documentation](https://docs.prefect.io/concepts/logs/#logging-print-statements) for more details.

See <https://github.com/PrefectHQ/prefect/pull/7580> for implementation details.

### Agent flow run concurrency limits

Agents can now limit the number of concurrent flow runs they are managing.

For example, start an agent with:

```
prefect agent start -q default --limit 10
```

When the agent submits a flow run, it will track it in a local concurrency slot. If the agent is managing more than 10 flow runs, the agent will not accept any more work from its work queues. When the infrastructure for a flow run exits, the agent will release a concurrency slot and another flow run can be submitted.

This feature is especially useful for limiting resource consumption when running flows locally! It also provides a way to roughly balance load across multiple agents.

Thanks to @eudyptula for contributing!

See <https://github.com/PrefectHQ/prefect/pull/7361> for more details.

### Enhancements

- Add agent reporting of crashed flow run infrastructure — <https://github.com/PrefectHQ/prefect/pull/7670>
- Add Twilio SMS notification block — <https://github.com/PrefectHQ/prefect/pull/7685>
- Add PagerDuty Webhook notification block — <https://github.com/PrefectHQ/prefect/pull/7534>
- Add jitter to the agent query loop — <https://github.com/PrefectHQ/prefect/pull/7652>
- Include final state logs in logs sent to API — <https://github.com/PrefectHQ/prefect/pull/7647>
- Add `tags` and `idempotency_key` to `run deployment` — <https://github.com/PrefectHQ/prefect/pull/7641>
- The final state of a flow is now `Cancelled` when any task finishes in a `Cancelled` state — <https://github.com/PrefectHQ/prefect/pull/7694>
- Update login to prompt for "API key" instead of "authentication key" — <https://github.com/PrefectHQ/prefect/pull/7649>
- Disable cache on result retrieval if disabled on creation — <https://github.com/PrefectHQ/prefect/pull/7627>
- Raise `CancelledRun` when retrieving a `Cancelled` state's result — <https://github.com/PrefectHQ/prefect/pull/7699>
- Use new database session to send each flow run notification — <https://github.com/PrefectHQ/prefect/pull/7644>
- Increase default agent query interval to 10s — <https://github.com/PrefectHQ/prefect/pull/7703>
- Add default messages to state exceptions — <https://github.com/PrefectHQ/prefect/pull/7705>
- Update `run_sync_in_interruptible_worker_thread` to use an event — <https://github.com/PrefectHQ/prefect/pull/7704>
- Increase default database query timeout to 10s — <https://github.com/PrefectHQ/prefect/pull/7717>

### Fixes

- Prompt workspace selection if API key is set, but API URL is not set — <https://github.com/PrefectHQ/prefect/pull/7648>
- Use `PREFECT_UI_URL` for flow run notifications — <https://github.com/PrefectHQ/prefect/pull/7698>
- Display all parameter values a flow run was triggered with in the UI (defaults and overrides) — <https://github.com/PrefectHQ/prefect/pull/7697>
- Fix bug where result event is missing when wait is called before submission completes — <https://github.com/PrefectHQ/prefect/pull/7571>
- Fix support for sync-compatible calls in `deployment build` — <https://github.com/PrefectHQ/prefect/pull/7417>
- Fix bug in `StateGroup` that caused `all_final` to be wrong — <https://github.com/PrefectHQ/prefect/pull/7678>
- Add retry on specified httpx network errors — <https://github.com/PrefectHQ/prefect/pull/7593>
- Fix state display bug when state message is empty — <https://github.com/PrefectHQ/prefect/pull/7706>

### Documentation

- Fix heading links in docs — <https://github.com/PrefectHQ/prefect/pull/7665>
- Update login and `PREFECT_API_URL` configuration notes — <https://github.com/PrefectHQ/prefect/pull/7674>
- Add documentation about AWS retries configuration — <https://github.com/PrefectHQ/prefect/pull/7691>
- Add GitLab storage block to deployment CLI docs — <https://github.com/PrefectHQ/prefect/pull/7686>
- Add links to Cloud Run and Container Instance infrastructure — <https://github.com/PrefectHQ/prefect/pull/7690>
- Update docs on final state determination to reflect `Cancelled` state changes — <https://github.com/PrefectHQ/prefect/pull/7700>
- Fix link in 'Agents and Work Queues' documentation — <https://github.com/PrefectHQ/prefect/pull/7659>

### Contributors

- @brian-pond made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7659>
- @YtKC made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7641>
- @eudyptula made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7361>
- @hateyouinfinity
- @jmrobbins13

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.9...2.7.0>

## Release 2.6.9

### Features

Logging into Prefect Cloud from the CLI has been given a serious upgrade!

<img width="748" alt="Login example" src="https://user-images.githubusercontent.com/2586601/199800241-c1b3691b-f18c-43ee-85e9-53cc3e5b1d48.png">

The `prefect cloud login` command now:

- Can be used non-interactively
- Can open the browser to generate a new API key for you
- Uses a new workspace selector
- Always uses your current profile
- Only prompts for workspace selection when you have more than one workspace

It also detects existing authentication:

- If logged in on the current profile, we will check that you want to reauthenticate
- If logged in on another profile, we will suggest a profile switch

There's also a new `prefect cloud logout` command (contributed by @hallenmaia) to remove credentials from the current profile.

### Enhancements

- Add automatic upper-casing of string log level settings — <https://github.com/PrefectHQ/prefect/pull/7592>
- Add `infrastructure_pid` to flow run — <https://github.com/PrefectHQ/prefect/pull/7595>
- Add `PrefectFormatter` to reduce logging configuration duplication — <https://github.com/PrefectHQ/prefect/pull/7588>
- Update `CloudClient.read_workspaces` to return a model — <https://github.com/PrefectHQ/prefect/pull/7332>
- Update hashing utilities to allow execution in FIPS 140-2 environments — <https://github.com/PrefectHQ/prefect/pull/7620>

### Fixes

- Update logging setup to support incremental configuration — <https://github.com/PrefectHQ/prefect/pull/7569>
- Update logging `JsonFormatter` to output valid JSON — <https://github.com/PrefectHQ/prefect/pull/7567>
- Remove `inter` CSS import, which blocked UI loads in air-gapped environments — <https://github.com/PrefectHQ/prefect/pull/7586>
- Return 404 when a flow run is missing during `set_task_run_state` — <https://github.com/PrefectHQ/prefect/pull/7603>
- Fix directory copy errors with `LocalFileSystem` deployments on Python 3.7 — <https://github.com/PrefectHQ/prefect/pull/7441>
- Add flush of task run logs when on remote workers — <https://github.com/PrefectHQ/prefect/pull/7626>

### Documentation

- Add docs about CPU and memory allocation on agent deploying ECS infrastructure blocks — <https://github.com/PrefectHQ/prefect/pull/7597>

### Contributors

- @hallenmaia
- @szelenka

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.8...2.6.9>

## Release 2.6.8

### Enhancements

- Add `--run-once` to `prefect agent start` CLI — <https://github.com/PrefectHQ/prefect/pull/7505>
- Expose `prefetch-seconds` in `prefect agent start` CLI — <https://github.com/PrefectHQ/prefect/pull/7498>
- Add start time sort for flow runs to the REST API — <https://github.com/PrefectHQ/prefect/pull/7496>
- Add `merge_existing_data` flag to `update_block_document` — <https://github.com/PrefectHQ/prefect/pull/7470>
- Add sanitization to enforce leading/trailing alphanumeric characters for Kubernetes job labels — <https://github.com/PrefectHQ/prefect/pull/7528>

### Fixes

- Fix type checking for flow name and version arguments — <https://github.com/PrefectHQ/prefect/pull/7549>
- Fix check for empty paths in `LocalFileSystem` — <https://github.com/PrefectHQ/prefect/pull/7477>
- Fix `PrefectConsoleHandler` bug where log tracebacks were excluded — <https://github.com/PrefectHQ/prefect/pull/7558>

### Documentation

- Add glow to Collection Catalog images in dark mode — <https://github.com/PrefectHQ/prefect/pull/7535>
- New [`prefect-vault`](https://github.com/pbchekin/prefect-vault) collection for integration with Hashicorp Vault

## Contributors

- @kielnino made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7517>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.7...2.6.8>

## Release 2.6.7

### Enhancements

- Add timeout support to tasks — <https://github.com/PrefectHQ/prefect/pull/7409>
- Add colored log levels — <https://github.com/PrefectHQ/prefect/pull/6101>
- Update flow and task run page sidebar styling — <https://github.com/PrefectHQ/prefect/pull/7426>
- Add redirect to logs tab when navigating to parent or child flow runs — <https://github.com/PrefectHQ/prefect/pull/7439>
- Add `PREFECT_UI_URL` and `PREFECT_CLOUD_UI_URL` settings — <https://github.com/PrefectHQ/prefect/pull/7411>
- Improve scheduler performance — <https://github.com/PrefectHQ/prefect/pull/7450> <https://github.com/PrefectHQ/prefect/pull/7433>
- Add link to parent flow from subflow details page — <https://github.com/PrefectHQ/prefect/pull/7491>
- Improve visibility of deployment tags in the deployments page — <https://github.com/PrefectHQ/prefect/pull/7491>
- Add deployment and flow metadata to infrastructure labels — <https://github.com/PrefectHQ/prefect/pull/7479>
- Add obfuscation of secret settings — <https://github.com/PrefectHQ/prefect/pull/7465>

### Fixes

- Fix missing import for `ObjectAlreadyExists` exception in deployments module — <https://github.com/PrefectHQ/prefect/pull/7360>
- Fix export of `State` and `allow_failure` for type-checkers  — <https://github.com/PrefectHQ/prefect/pull/7447>
- Fix `--skip-upload` flag in `prefect deployment build` — <https://github.com/PrefectHQ/prefect/pull/7437>
- Fix `visit_collection` handling of IO objects — <https://github.com/PrefectHQ/prefect/pull/7482>
- Ensure that queries are sorted correctly when limits are used — <https://github.com/PrefectHQ/prefect/pull/7457>

### Deprecations

- `PREFECT_CLOUD_URL` has been deprecated in favor of `PREFECT_CLOUD_API_URL` — <https://github.com/PrefectHQ/prefect/pull/7411>
- `prefect.orion.utilities.names` has been deprecated in favor of `prefect.utilities.names` — <https://github.com/PrefectHQ/prefect/pull/7465>

### Documentation

- Add support for dark mode — <https://github.com/PrefectHQ/prefect/pull/7432> and <https://github.com/PrefectHQ/prefect/pull/7462>
- Add [audit log documentation](https://docs.prefect.io/ui/audit-log/) for Prefect Cloud — <https://github.com/PrefectHQ/prefect/pull/7404>
- Add [troubleshooting topics](https://docs.prefect.io/ui/troubleshooting/) for Prefect Cloud — <https://github.com/PrefectHQ/prefect/pull/7446>

### Collections

- Adds auto-registration of blocks from AWS, Azure, GCP, and Databricks collections — <https://github.com/PrefectHQ/prefect/pull/7415>
- Add new [`prefect-hightouch`](https://prefecthq.github.io/prefect-hightouch/) collection for [Hightouch](https://hightouch.com/) — <https://github.com/PrefectHQ/prefect/pull/7443>

### Contributors

- @tekumara
- @bcbernardo made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7360>
- @br3ndonland made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7432>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.6...2.6.7>

## Release 2.6.6

### Enhancements

- Add work queue status and health display to UI — [#733](https://github.com/PrefectHQ/orion-design/pull/733), [#743](https://github.com/PrefectHQ/orion-design/pull/743), [#750](https://github.com/PrefectHQ/orion-design/pull/750)
- Add `wait_for` to flows; subflows can wait for upstream tasks — <https://github.com/PrefectHQ/prefect/pull/7343>
- Add informative error if flow run is deleted while running — <https://github.com/PrefectHQ/prefect/pull/7390>
- Add name filtering support to the `work_queues/filter` API route — <https://github.com/PrefectHQ/prefect/pull/7394>
- Improve the stability of the scheduler service — <https://github.com/PrefectHQ/prefect/pull/7412>

### Fixes

- Fix GitHub storage error for Windows — <https://github.com/PrefectHQ/prefect/pull/7372>
- Fix links to flow runs in notifications — <https://github.com/PrefectHQ/prefect/pull/7249>
- Fix link to UI deployment page in CLI — <https://github.com/PrefectHQ/prefect/pull/7376>
- Fix UI URL routing to be consistent with CLI — <https://github.com/PrefectHQ/prefect/pull/7391>
- Assert that command is a list when passed to `open_process` — <https://github.com/PrefectHQ/prefect/pull/7389>
- Fix JSON error when serializing certain flow run parameters such as dataframes — <https://github.com/PrefectHQ/prefect/pull/7385>

### Documentation

- Add versioning documentation — <https://github.com/PrefectHQ/prefect/pull/7353>

### Collections

- New [`prefect-alert`](https://github.com/khuyentran1401/prefect-alert) collection for sending alerts on flow run fail
- New [Fivetran](https://fivetran.github.io/prefect-fivetran/) collection
- New [GitLab](https://prefecthq.github.io/prefect-gitlab/) collection

## Contributors

- @marwan116

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.5...2.6.6>

## Release 2.6.5

### Enhancements

- Add support for manual flow run retries — <https://github.com/PrefectHQ/prefect/pull/7152>
- Improve server performance when retrying flow runs with many tasks — <https://github.com/PrefectHQ/prefect/pull/7152>
- Add status checks to work queues — <https://github.com/PrefectHQ/prefect/pull/7262>
- Add timezone parameter to `prefect deployment build` — <https://github.com/PrefectHQ/prefect/pull/7282>
- UI: Add redirect to original block form after creating a nested block — <https://github.com/PrefectHQ/prefect/pull/7284>
- Add support for multiple work queue prefixes — <https://github.com/PrefectHQ/prefect/pull/7222>
- Include "-" before random suffix of Kubernetes job names — <https://github.com/PrefectHQ/prefect/pull/7329>
- Allow a working directory to be specified for `Process` infrastructure — <https://github.com/PrefectHQ/prefect/pull/7252>
- Add support for Python 3.11 — <https://github.com/PrefectHQ/prefect/pull/7304>
- Add persistence of data when a state is returned from a task or flow — <https://github.com/PrefectHQ/prefect/pull/7316>
- Add `ignore_file` to `Deployment.build_from_flow()` — <https://github.com/PrefectHQ/prefect/pull/7012>

### Fixes

- Allow `with_options` to reset retries and retry delays — <https://github.com/PrefectHQ/prefect/pull/7276>
- Fix proxy-awareness in the `OrionClient` — <https://github.com/PrefectHQ/prefect/pull/7328>
- Fix block auto-registration when changing databases — <https://github.com/PrefectHQ/prefect/pull/7350>
- Include hidden files when uploading directories to `RemoteFileSystem` storage — <https://github.com/PrefectHQ/prefect/pull/7336>
- UI: added support for unsetting color-mode preference, `null` is now equivalent to "default" — <https://github.com/PrefectHQ/prefect/pull/7321>

### Documentation

- Add documentation for Prefect Cloud SSO — <https://github.com/PrefectHQ/prefect/pull/7302>

### Collections

- New [`prefect-docker`](https://prefecthq.github.io/prefect-docker/) collection for [Docker](https://www.docker.com/)
- New [`prefect-census`](https://prefecthq.github.io/prefect-census/) collection for [Census](https://docs.getcensus.com/)

## Contributors

- @BallisticPain made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7252>
- @deepyaman
- @hateyouinfinity
- @jmg-duarte
- @taljaards

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.4...2.6.5>

## Release 2.6.4

### Enhancements

- UI: Rename deployment "Overview" tab to "Description" — <https://github.com/PrefectHQ/prefect/pull/7234>
- Add `Deployment.build_from_flow` toggle to disable loading of existing values from the API — <https://github.com/PrefectHQ/prefect/pull/7218>
- Add `PREFECT_RESULTS_PERSIST_BY_DEFAULT` setting to globally toggle the result persistence default — <https://github.com/PrefectHQ/prefect/pull/7228>
- Add support for using callable objects as tasks — <https://github.com/PrefectHQ/prefect/pull/7217>
- Add authentication as service principal to the `Azure` storage block — <https://github.com/PrefectHQ/prefect/pull/6844>
- Update default database timeout from 1 to 5 seconds — <https://github.com/PrefectHQ/prefect/pull/7246>

### Fixes

- Allow image/namespace fields to be loaded from Kubernetes job manifest — <https://github.com/PrefectHQ/prefect/pull/7244>
- UI: Update settings API call to respect `ORION_UI_SERVE_BASE` environment variable — <https://github.com/PrefectHQ/prefect/pull/7068>
- Fix entrypoint path error when deployment is created on Windows then run on Unix — <https://github.com/PrefectHQ/prefect/pull/7261>

### Collections

- New [`prefect-kv`](https://github.com/madkinsz/prefect-kv) collection for persisting key-value data
- `prefect-aws`: Update [`S3Bucket`](https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.s3.S3Bucket) storage block to enable use with deployments — <https://github.com/PrefectHQ/prefect-aws/pull/82>
- `prefect-aws`: Add support for arbitrary user customizations to [`ECSTask`](https://prefecthq.github.io/prefect-aws/ecs/) block — <https://github.com/PrefectHQ/prefect-aws/pull/120>
- `prefect-aws`: Removed the experimental designation from the [`ECSTask`](https://prefecthq.github.io/prefect-aws/ecs/) block
- `prefect-azure`: New [`AzureContainerInstanceJob`](https://prefecthq.github.io/prefect-azure/container_instance/) infrastructure block to run flows or commands as containers on Azure — <https://github.com/PrefectHQ/prefect-azure/pull/45>

### Contributors

- @Trymzet
- @jmg-duarte
- @mthanded made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7068>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.3...2.6.4>

## Release 2.6.3

### Fixes

- Fix handling of `cache_result_in_memory` in `Task.with_options` — <https://github.com/PrefectHQ/prefect/pull/7227>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.2...2.6.3>

## Release 2.6.2

### Enhancements

- Add `CompressedSerializer` for compression of other result serializers — <https://github.com/PrefectHQ/prefect/pull/7164>
- Add option to drop task or flow return values from memory — <https://github.com/PrefectHQ/prefect/pull/7174>
- Add support for creating and reading notification policies from the client — <https://github.com/PrefectHQ/prefect/pull/7154>
- Add API support for sorting deployments — <https://github.com/PrefectHQ/prefect/pull/7187>
- Improve searching and sorting of flows and deployments in the UI —  <https://github.com/PrefectHQ/prefect/pull/7160>
- Improve recurrence rule schedule parsing with support for compound rules  — <https://github.com/PrefectHQ/prefect/pull/7165>
- Add support for private GitHub repositories — <https://github.com/PrefectHQ/prefect/pull/7107>

### Fixes

- Improve orchestration handling of `after_transition` when exception encountered — <https://github.com/PrefectHQ/prefect/pull/7156>
- Prevent block name from being reused on the block creation form in the UI — <https://github.com/PrefectHQ/prefect/pull/7096>
- Fix bug where `with_options` incorrectly updates result settings — <https://github.com/PrefectHQ/prefect/pull/7186>
- Add backwards compatibility for return of server-states from flows and tasks — <https://github.com/PrefectHQ/prefect/pull/7189>
- Fix naming of subflow runs tab on flow run page in the UI — <https://github.com/PrefectHQ/prefect/pull/7192>
- Fix `prefect orion start` error on Windows when module path contains spaces — <https://github.com/PrefectHQ/prefect/pull/7224>

### Collections

- New [prefect-monte-carlo](https://prefecthq.github.io/prefect-monte-carlo/) collection for interaction with [Monte Carlo](https://www.montecarlodata.com/)

### Contributors

- @jmg-duarte

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.1...2.6.2>

## Release 2.6.1

### Fixes

- Fix bug where return values of `{}` or `[]` could be coerced to `None` — <https://github.com/PrefectHQ/prefect/pull/7181>

## Contributors

- @acookin made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7172>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.6.0...2.6.1>

## Release 2.6.0

### First-class configuration of results 🎉

Previously, Prefect serialized the results of all flows and tasks with pickle, then wrote them to your local file system.
In this release, we're excited to announce this behavior is fully configurable and customizable.

Here are some highlights:

- Persistence of results is off by default.
    — We will turn on result persistence automatically if needed for a feature you're using, but you can always opt-out.
    — You can easily opt-in for any flow or task.
- You can choose the result serializer.
    — By default, we continue to use a pickle serializer, now with the ability to choose a custom implementation.
    — We now offer a JSON result serializer with support for all of the types supported by Pydantic.
    — You can also write your own serializer for full control.
    — Unless your results are being persisted, they will not be serialized.
- You can change the result storage.
    — By default, we will continue to use the local file system.
    — You can specify any of our storage blocks, such as AWS S3.
    — You can use any storage block you have defined.

All of the options can be customized per flow or task.

```python
from prefect import flow, task

# This flow defines a default result serializer for itself and all tasks in it
@flow(result_serializer="pickle")
def foo():
    one()
    two()
    three()

# This task's result will be persisted to the local file system
@task(persist_result=True)
def one():
    return "one!"

# This task will not persist its result
@task(persist_result=False)
def two():
    return "two!"

# This task will use a different serializer than the rest
@task(persist_result=True, result_serializer="json")
def three():
    return "three!"

# This task will persist its result to an S3 bucket
@task(persist_result=True, result_storage="s3/my-s3-block")
def four()
    return "four!
```

See the [documentation](https://docs.prefect.io/concepts/results/) for more details and examples.
See <https://github.com/PrefectHQ/prefect/pull/6908> for implementation details.

### Waiting for tasks even if they fail

You can now specify that a downstream task should wait for an upstream task and run even if the upstream task has failed.

```python
from prefect import task, flow, allow_failure

@flow
def foo():
    upstream_future = fails_sometimes.submit()
    important_cleanup(wait_for=[allow_failure(upstream_future)])

@task
def fails_sometimes():
    raise RuntimeError("oh no!")

@task
def important_cleanup():
    ...
```

See <https://github.com/PrefectHQ/prefect/pull/7120> for implementation details.

### Work queue match support for agents

Agents can now match multiple work queues by providing a `--match` string instead of specifying all of the work queues. The agent will poll every work queue with a name that starts with the given string. Your agent will detect new work queues that match the option without requiring a restart!

```
prefect agent start --match "foo-"
```

### Enhancements

- Add `--param` / `--params` support `prefect deployment run` — <https://github.com/PrefectHQ/prefect/pull/7018>
- Add 'Show Active Runs' button to work queue page — <https://github.com/PrefectHQ/prefect/pull/7092>
- Update block protection to only prevent deletion — <https://github.com/PrefectHQ/prefect/pull/7042>
- Improve stability by optimizing the HTTP client — <https://github.com/PrefectHQ/prefect/pull/7090>
- Optimize flow run history queries — <https://github.com/PrefectHQ/prefect/pull/7138>
- Optimize server handling by saving log batches in individual transactions — <https://github.com/PrefectHQ/prefect/pull/7141>
- Optimize deletion of auto-scheduled runs — <https://github.com/PrefectHQ/prefect/pull/7102>

### Fixes

- Fix `DockerContainer` log streaming crash due to "marked for removal" error — <https://github.com/PrefectHQ/prefect/pull/6860>
- Improve RRule schedule string parsing — <https://github.com/PrefectHQ/prefect/pull/7133>
- Improve handling of duplicate blocks, reducing errors in server logs — <https://github.com/PrefectHQ/prefect/pull/7140>
- Fix flow run URLs in notifications and `prefect deployment run` output — <https://github.com/PrefectHQ/prefect/pull/7153>

### Documentation

- Add documentation for support of proxies — <https://github.com/PrefectHQ/prefect/pull/7087>
- Fix rendering of Prefect settings in API reference — <https://github.com/PrefectHQ/prefect/pull/7067>

### Contributors

- @jmg-duarte

- @kevin868 made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7109>
- @space-age-pete made their first contribution in <https://github.com/PrefectHQ/prefect/pull/7122>

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.5.0...2.6.0>

## Release 2.5.0

### Exciting New Features 🎉

- Add `prefect.deployments.run_deployment` to create a flow run for a deployment with support for:
    — Configurable execution modes: returning immediately or waiting for completion of the run.
    — Scheduling runs in the future or now.
    — Custom flow run names.
    — Automatic linking of created flow run to the flow run it is created from.
    — Automatic tracking of upstream task results passed as parameters.
  <br />
  See <https://github.com/PrefectHQ/prefect/pull/7047>, <https://github.com/PrefectHQ/prefect/pull/7081>, and <https://github.com/PrefectHQ/prefect/pull/7084>

### Enhancements

- Add ability to delete multiple objects on flow run, flow, deployment and work queue pages — <https://github.com/PrefectHQ/prefect/pull/7086>
- Update `put_directory` to exclude directories from upload counts — <https://github.com/PrefectHQ/prefect/pull/7054>
- Always suppress griffe logs — <https://github.com/PrefectHQ/prefect/pull/7059>
- Add OOM warning to `Process` exit code log message — <https://github.com/PrefectHQ/prefect/pull/7070>
- Add idempotency key support to `OrionClient.create_flow_run_from_deployment` — <https://github.com/PrefectHQ/prefect/pull/7074>

### Fixes

- Fix default start date filter for deployments page in UI — <https://github.com/PrefectHQ/prefect/pull/7025>
- Fix `sync_compatible` handling of wrapped async functions and generators — <https://github.com/PrefectHQ/prefect/pull/7009>
- Fix bug where server could error due to an unexpected null in task caching logic — <https://github.com/PrefectHQ/prefect/pull/7031>
- Add exception handling to block auto-registration — <https://github.com/PrefectHQ/prefect/pull/6997>
- Remove the "sync caller" check from `sync_compatible` — <https://github.com/PrefectHQ/prefect/pull/7073>

### Documentation

- Add `ECSTask` block tutorial to recipes — <https://github.com/PrefectHQ/prefect/pull/7066>
- Update documentation for organizations for member management, roles, and permissions — <https://github.com/PrefectHQ/prefect/pull/7058>

## Collections

- New [prefect-soda-core](https://sodadata.github.io/prefect-soda-core/) collection for integration with [Soda](https://www.soda.io/).

### Contributors

- @taljaards

**All changes**: <https://github.com/PrefectHQ/prefect/compare/2.4.5...2.5.0>

## Release 2.4.5

This release disables block protection. With block protection enabled, as in 2.4.3 and 2.4.4, client and server versions cannot be mismatched unless you are on a version before 2.4.0. Disabling block protection restores the ability for a client and server to have different version.

Block protection was added in 2.4.1 to prevent users from deleting block types that are necessary for the system to function. With this change, you are able to delete block types that will cause your flow runs to fail. New safeguards that do not affect client/server compatibility will be added in the future.

## Release 2.4.3

**When running a server with this version, the client must be the same version. This does not apply to clients connecting to Prefect Cloud.**

### Enhancements

- Warn if user tries to login with API key from Cloud 1 — <https://github.com/PrefectHQ/prefect/pull/6958>
- Improve concurrent task runner performance — <https://github.com/PrefectHQ/prefect/pull/6948>
- Raise a `MissingContextError` when `get_run_logger` is called outside a run context — <https://github.com/PrefectHQ/prefect/pull/6980>
- Adding caching to API configuration lookups to improve performance — <https://github.com/PrefectHQ/prefect/pull/6959>
- Move `quote` to `prefect.utilities.annotations` — <https://github.com/PrefectHQ/prefect/pull/6993>
- Add state filters and sort-by to the work-queue, flow and deployment pages — <https://github.com/PrefectHQ/prefect/pull/6985>

### Fixes

- Fix login to private Docker registries — <https://github.com/PrefectHQ/prefect/pull/6889>
- Update `Flow.with_options` to actually pass retry settings to new object — <https://github.com/PrefectHQ/prefect/pull/6963>
- Fix compatibility for protected blocks when client/server versions are mismatched — <https://github.com/PrefectHQ/prefect/pull/6986>
- Ensure `python-slugify` is always used even if [unicode-slugify](https://github.com/mozilla/unicode-slugify) is installed — <https://github.com/PrefectHQ/prefect/pull/6955>

### Documentation

- Update documentation for specifying schedules from the CLI — <https://github.com/PrefectHQ/prefect/pull/6968>
- Add results concept to documentation — <https://github.com/PrefectHQ/prefect/pull/6992>

### Collections

- New [`prefect-hex` collection](https://prefecthq.github.io/prefect-hex/) — <https://github.com/PrefectHQ/prefect/pull/6974>
- New [`CloudRunJob` infrastructure block](https://prefecthq.github.io/prefect-gcp/cloud_run/) in `prefect-gcp` — <https://github.com/PrefectHQ/prefect-gcp/pull/48>

### Contributors

- @Hongbo-Miao made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6956>

- @hateyouinfinity made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6955>

## Release 2.4.2

### Fixes

- Remove types in blocks docstring attributes to avoid annotation parsing warnings — <https://github.com/PrefectHQ/prefect/pull/6937>
- Fixes `inject_client` in scenarios where the `client` kwarg is passed `None` — <https://github.com/PrefectHQ/prefect/pull/6942>

### Contributors

- @john-jam made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6937>

## Release 2.4.1

### Enhancements

- Add TTL to `KubernetesJob` for automated cleanup of finished jobs — <https://github.com/PrefectHQ/prefect/pull/6785>
- Add `prefect kubernetes manifest agent` to generate an agent Kubernetes manifest — <https://github.com/PrefectHQ/prefect/pull/6771>
- Add `prefect block type delete` to delete block types — <https://github.com/PrefectHQ/prefect/pull/6849>
- Add dynamic titles to tabs in UI — <https://github.com/PrefectHQ/prefect/pull/6914>
- Hide secret tails by default — <https://github.com/PrefectHQ/prefect/pull/6846>
- Add runs tab to show flow runs on the flow, deployment, and work-queue pages in the UI — <https://github.com/PrefectHQ/prefect/pull/6721>
- Add toggle to disable block registration on application start — <https://github.com/PrefectHQ/prefect/pull/6858>
- Use injected client during block registration, save, and load — <https://github.com/PrefectHQ/prefect/pull/6857>
- Refactor of `prefect.client` into `prefect.client.orion` and `prefect.client.cloud` — <https://github.com/PrefectHQ/prefect/pull/6847>
- Improve breadcrumbs on radar page in UI — <https://github.com/PrefectHQ/prefect/pull/6757>
- Reject redundant state transitions to prevent duplicate runs — <https://github.com/PrefectHQ/prefect/pull/6852>
- Update block auto-registration to use a cache to improve performance — <https://github.com/PrefectHQ/prefect/pull/6841>
- Add ability to define blocks from collections to be registered by default — <https://github.com/PrefectHQ/prefect/pull/6890>
- Update file systems interfaces to be sync compatible — <https://github.com/PrefectHQ/prefect/pull/6511>
- Add flow run URLs to notifications — <https://github.com/PrefectHQ/prefect/pull/6798>
- Add client retries on 503 responses — <https://github.com/PrefectHQ/prefect/pull/6927>
- Update injected client retrieval to use the flow and task run context client for reduced overhead — <https://github.com/PrefectHQ/prefect/pull/6859>
- Add Microsoft Teams notification block — <https://github.com/PrefectHQ/prefect/pull/6920>

### Fixes

- Fix `LocalFileSystem.get_directory` when from and to paths match — <https://github.com/PrefectHQ/prefect/pull/6824>
- Fix registration of block schema versions — <https://github.com/PrefectHQ/prefect/pull/6803>
- Update agent to capture infrastructure errors and fail the flow run instead of crashing — <https://github.com/PrefectHQ/prefect/pull/6903>
- Fix bug where `OrionClient.read_logs` filter was ignored — <https://github.com/PrefectHQ/prefect/pull/6885>

### Documentation

- Add GitHub and Docker deployment recipe — <https://github.com/PrefectHQ/prefect/pull/6825>
- Add parameter configuration examples — <https://github.com/PrefectHQ/prefect/pull/6886>

### Collections

- Add `prefect-firebolt` to collections catalog — <https://github.com/PrefectHQ/prefect/pull/6917>

### Helm Charts

- Major overhaul in how helm charts in `prefect-helm` are structured and how we version and release them — [2022.09.21 release](https://github.com/PrefectHQ/prefect-helm/releases/tag/2022.09.21)

### Contributors

- @jmg-duarte
- @taljaards
- @yashlad681
- @hallenmaia made their first contributions(!) in <https://github.com/PrefectHQ/prefect/pull/6903>, <https://github.com/PrefectHQ/prefect/pull/6785>, and <https://github.com/PrefectHQ/prefect/pull/6771>
- @dobbersc made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6870>
- @jnovinger made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6916>
- @mathijscarlu made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6885>

## Release 2.4.0

### Exciting New Features 🎉

- Add `ECSTask` infrastructure block to run commands and flows on AWS ECS<br />
    See [the documentation](https://prefecthq.github.io/prefect-aws/ecs/) in the [prefect-aws collection](https://prefecthq.github.io/prefect-aws/) and usage notes in the [infrastructure guide](https://docs.prefect.io/concepts/infrastructure/#ecstask)

### Enhancements

- Update the deployments CLI to better support CI/CD use cases — <https://github.com/PrefectHQ/prefect/pull/6697>
- Improve database query performance by removing unnecessary SQL transactions — <https://github.com/PrefectHQ/prefect/pull/6714>
- Update blocks to dispatch instance creation using slugs — <https://github.com/PrefectHQ/prefect/pull/6622>
- Add flow run start times to flow run metadata in UI — <https://github.com/PrefectHQ/prefect/pull/6743>
- Update default infrastructure command to be set at runtime — <https://github.com/PrefectHQ/prefect/pull/6610>
- Allow environment variables to be "unset" in infrastructure blocks — <https://github.com/PrefectHQ/prefect/pull/6650>
- Add favicon switching feature for flow and task run pages — <https://github.com/PrefectHQ/prefect/pull/6794>
- Update `Deployment.infrastructure` to accept types outside of the core library i.e. custom infrastructure or from collections — <https://github.com/PrefectHQ/prefect/pull/6674>
- Update `deployment build --rrule` input to allow start date and timezones — <https://github.com/PrefectHQ/prefect/pull/6761>

### Fixes

- Update crash detection to ignore abort signals — <https://github.com/PrefectHQ/prefect/pull/6730>
- Protect against race condition with deployment schedules — <https://github.com/PrefectHQ/prefect/pull/6673>
- Fix saving of block fields with aliases — <https://github.com/PrefectHQ/prefect/pull/6758>
- Preserve task dependencies to futures passed as parameters in `.map` — <https://github.com/PrefectHQ/prefect/pull/6701>
- Update task run orchestration to include latest metadata in context — <https://github.com/PrefectHQ/prefect/pull/6791>

### Documentation

- Task runner documentation fixes and clarifications — <https://github.com/PrefectHQ/prefect/pull/6733>
- Add notes for Windows and Linux installation — <https://github.com/PrefectHQ/prefect/pull/6750>
- Add a catalog of implementation recipes — <https://github.com/PrefectHQ/prefect/pull/6408>
- Improve storage and file systems documentation — <https://github.com/PrefectHQ/prefect/pull/6756>
- Add CSS for badges — <https://github.com/PrefectHQ/prefect/pull/6655>

### Contributors

- @robalar made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6701>

- @shraddhafalane made their first contribution in <https://github.com/PrefectHQ/prefect/pull/6784>

## 2.3.2

### Enhancements

- UI displays an error message when backend is unreachable — <https://github.com/PrefectHQ/prefect/pull/6670>

### Fixes

- Fix issue where parameters weren't updated when a deployment was re-applied by @lennertvandevelde in <https://github.com/PrefectHQ/prefect/pull/6668>

- Fix issues with stopping Orion on Windows machines — <https://github.com/PrefectHQ/prefect/pull/6672>
- Fix issue with GitHub storage running in non-empty directories — <https://github.com/PrefectHQ/prefect/pull/6693>
- Fix issue where some user-supplied values were ignored when creating new deployments — <https://github.com/PrefectHQ/prefect/pull/6695>

### Collections

- Added [prefect-fugue](https://fugue-project.github.io/prefect-fugue/)

### Contributors

- @lennertvandevelde made their first contribution! — [https://github.com/PrefectHQ/prefect/pull/6668](https://github.com/PrefectHQ/prefect/pull/6668)

## 2.3.1

### Enhancements

- Add sync compatibility to `run` for all infrastructure types — <https://github.com/PrefectHQ/prefect/pull/6654>

- Update Docker container name collision log to `INFO` level for clarity — <https://github.com/PrefectHQ/prefect/pull/6657>
- Refactor block documents queries for speed ⚡️ — <https://github.com/PrefectHQ/prefect/pull/6645>
- Update block CLI to match standard styling — <https://github.com/PrefectHQ/prefect/pull/6679>

### Fixes

- Add `git` to the Prefect image — <https://github.com/PrefectHQ/prefect/pull/6653>

- Update Docker container runs to be robust to container removal — <https://github.com/PrefectHQ/prefect/pull/6656>
- Fix parsing of `PREFECT_TEST_MODE` in `PrefectBaseModel` — <https://github.com/PrefectHQ/prefect/pull/6647>
- Fix handling of `.prefectignore` paths on Windows — <https://github.com/PrefectHQ/prefect/pull/6680>

### Collections

- [prefect-juptyer](https://prefecthq.github.io/prefect-jupyter/)

### Contributors

- @mars-f made their first contribution — <https://github.com/PrefectHQ/prefect/pull/6639>

- @pdashk made their first contribution — <https://github.com/PrefectHQ/prefect/pull/6640>

## 2.3.0

### Exciting New Features 🎉

- Add support for deploying flows stored in Docker images — [#6574](https://github.com/PrefectHQ/prefect/pull/6574)
- Add support for deploying flows stored on GitHub — [#6598](https://github.com/PrefectHQ/prefect/pull/6598)
- Add file system block for reading directories from GitHub — [#6517](https://github.com/PrefectHQ/prefect/pull/6517)
- Add a context manager to disable the flow and task run loggers for testing — [#6575](https://github.com/PrefectHQ/prefect/pull/6575)
- Add task run pages to the UI — [#6570](https://github.com/PrefectHQ/prefect/pull/6570)

### Enhancements

- Add "cloud" to `prefect version` server type display — [#6523](https://github.com/PrefectHQ/prefect/pull/6523)
- Use the parent flow run client for child flow runs if available — [#6526](https://github.com/PrefectHQ/prefect/pull/6526)
- Add display of Prefect version when starting agent — [#6545](https://github.com/PrefectHQ/prefect/pull/6545)
- Add type hints to state predicates, e.g. `is_completed()` — [#6561](https://github.com/PrefectHQ/prefect/pull/6561)
- Add error when sync compatible methods are used incorrectly — [#6565](https://github.com/PrefectHQ/prefect/pull/6565)
- Improve performance of task run submission — [#6527](https://github.com/PrefectHQ/prefect/pull/6527)
- Improve performance of flow run serialization for `/flow_runs/filter` endpoint — [#6553](https://github.com/PrefectHQ/prefect/pull/6553)
- Add field to states with untrackable dependencies due to result types — [#6472](https://github.com/PrefectHQ/prefect/pull/6472)
- Update `Task.map` iterable detection to exclude strings and bytes — [#6582](https://github.com/PrefectHQ/prefect/pull/6582)
- Add a version attribute to the block schema model — [#6491](https://github.com/PrefectHQ/prefect/pull/6491)
- Add better error handling in the telemetry service — [#6124](https://github.com/PrefectHQ/prefect/pull/6124)
- Update the Docker entrypoint display for the Prefect image — [#655](https://github.com/PrefectHQ/prefect/pull/6552)
- Add a block creation link to `prefect block type ls` — [#6493](https://github.com/PrefectHQ/prefect/pull/6493)
- Allow customization of notifications of queued flow runs — [#6538](https://github.com/PrefectHQ/prefect/pull/6538)
- Avoid duplicate saves of storage blocks as anonymous blocks — [#6550](https://github.com/PrefectHQ/prefect/pull/6550)
- Remove save of agent default infrastructure blocks — [#6550](https://github.com/PrefectHQ/prefect/pull/6550)
- Add a `--skip-upload` flag to `prefect deployment build` — [#6560](https://github.com/PrefectHQ/prefect/pull/6560)
- Add a `--upload` flag to `prefect deployment apply` — [#6560](https://github.com/PrefectHQ/prefect/pull/6560)
- Add the ability to specify relative sub-paths when working with remote storage for deployments — [#6518](https://github.com/PrefectHQ/prefect/pull/6518)
- Prevent non-UUID slugs from raising errors on `/block_document` endpoints — [#6541](https://github.com/PrefectHQ/prefect/pull/6541)
- Improve Docker image tag parsing to support the full Moby specification — [#6564](https://github.com/PrefectHQ/prefect/pull/6564)

### Fixes

- Set uvicorn `--app-dir` when starting Orion to avoid module collisions — [#6547](https://github.com/PrefectHQ/prefect/pull/6547)
- Resolve issue with Python-based deployments having incorrect entrypoint paths — [#6554](https://github.com/PrefectHQ/prefect/pull/6554)
- Fix Docker image tag parsing when ports are included — [#6567](https://github.com/PrefectHQ/prefect/pull/6567)
- Update Kubernetes Job to use `args` instead of `command` to respect image entrypoints — [#6581](https://github.com/PrefectHQ/prefect/pull/6581)
    — Warning: If you are using a custom image with an entrypoint that does not allow passthrough of commands, flow runs will fail.
- Fix edge case in `sync_compatible` detection when using AnyIO task groups — [#6602](https://github.com/PrefectHQ/prefect/pull/6602)
- Add check for infrastructure and storage block capabilities during deployment build — [#6535](https://github.com/PrefectHQ/prefect/pull/6535)
- Fix issue where deprecated work queue pages showed multiple deprecation notices — [#6531](https://github.com/PrefectHQ/prefect/pull/6531)
- Fix path issues with `RemoteFileSystem` and Windows — [#6620](https://github.com/PrefectHQ/prefect/pull/6620)
- Fix a bug where `RemoteFileSystem.put_directory` did not respect `local_path` — [#6620](https://github.com/PrefectHQ/prefect/pull/6620)

### Documentation

- Add tutorials for creating and using storage and infrastructure blocks — [#6608](https://github.com/PrefectHQ/prefect/pull/6608)
- Update tutorial for running flows in Docker — [#6612](https://github.com/PrefectHQ/prefect/pull/6612)
- Add example of calling a task from a task — [#6501](https://github.com/PrefectHQ/prefect/pull/6501)
- Update database documentation for Postgres to clarify required plugins — [#6566](https://github.com/PrefectHQ/prefect/pull/6566)
- Add example of using `Task.map` in docstring — [#6579](https://github.com/PrefectHQ/prefect/pull/6579)
- Add details about flow run retention policies — [#6577](https://github.com/PrefectHQ/prefect/pull/6577)
- Fix flow parameter name docstring in deployments — [#6599](https://github.com/PrefectHQ/prefect/pull/6599)

### Contributors

Thanks to our external contributors!

- @darrida
- @jmg-duarte
- @MSSandroid

## 2.2.0

### Exciting New Features 🎉

- Added automatic detection of static arguments to `Task.map` in <https://github.com/PrefectHQ/prefect/pull/6513>

### Fixes

- Updated deployment flow run retry settings with runtime values in <https://github.com/PrefectHQ/prefect/pull/6489>

- Updated media queries for flow-run-filter in <https://github.com/PrefectHQ/prefect/pull/6484>
- Added `empirical_policy` to flow run update route in <https://github.com/PrefectHQ/prefect/pull/6486>
- Updated flow run policy retry settings to be nullable in <https://github.com/PrefectHQ/prefect/pull/6488>
- Disallowed extra attribute initialization on `Deployment` objects in <https://github.com/PrefectHQ/prefect/pull/6505>
- Updated `deployment build` to raise an informative error if two infrastructure configs are provided in <https://github.com/PrefectHQ/prefect/pull/6504>
- Fixed calling async subflows from sync parents in <https://github.com/PrefectHQ/prefect/pull/6514>

## 2.1.1

### Fixes

- Fixed log on abort when the flow run context is not available in <https://github.com/PrefectHQ/prefect/pull/6402>
- Fixed error message in `submit_run` in <https://github.com/PrefectHQ/prefect/pull/6453>
- Fixed error if default parameters are missing on a deployment flow run in <https://github.com/PrefectHQ/prefect/pull/6465>
- Added error message if `get_run_logger` receives context of unknown type in <https://github.com/PrefectHQ/prefect/pull/6401>

## 2.1.0

### Build Deployments in Python

The new, YAML-based deployment definition provides a simple, extensible foundation for our new deployment creation experience. Now, by popular demand, we're extending that experience to enable you to define deployments and build them from within Python. You can do so by defining a `Deployment` Python object, specifying the deployment options as properties of the object, then building and applying the object using methods of `Deployment`. See the [documentation](https://docs.prefect.io/concepts/deployments/) to learn more.

### Simplified Agents & Work Queues

Agents and work queues give you control over where and how flow runs are executed. Now, creating an agent (and corresponding work queue) is even easier. Work queues now operate strictly by name, not by matching tags. Deployments, and the flow runs they generate, are explicitly linked to a single work queue, and the work queue is automatically created whenever a deployment references it. This means you no longer need to manually create a new work queue each time you want to want to route a deployment's flow runs separately. Agents can now pull from multiple work queues, and also automatically generate work queues that don't already exist. The result of these improvements is that most users will not have to interact directly with work queues at all, but advanced users can take advantage of them for increased control over how work is distributed to agents. These changes are fully backwards compatible. See the [documentation](https://docs.prefect.io/concepts/work-queues/) to learn more.

### Improvements and bug fixes

- Added three new exceptions to improve errors when parameters are incorrectly supplied to flow runs in <https://github.com/PrefectHQ/prefect/pull/6091>

- Fixed a task dependency issue where unpacked values were not being correctly traced in <https://github.com/PrefectHQ/prefect/pull/6348>
- Added the ability to embed `BaseModel` subclasses as fields within blocks, resolving an issue with the ImagePullPolicy field on the KubernetesJob block in <https://github.com/PrefectHQ/prefect/pull/6389>
- Added comments support for deployment.yaml to enable inline help in <https://github.com/PrefectHQ/prefect/pull/6339>
- Added support for specifying three schedule types — cron, interval and rrule — to the `deployment build` CLI in <https://github.com/PrefectHQ/prefect/pull/6387>
- Added error handling for exceptions raised during the pre-transition hook fired by an OrchestrationRule during state transitions in <https://github.com/PrefectHQ/prefect/pull/6315>
- Updated `visit_collection` to be a synchronous function in <https://github.com/PrefectHQ/prefect/pull/6371>
- Revised loop service method names for clarity in <https://github.com/PrefectHQ/prefect/pull/6131>
- Modified deployments to load flows in a worker thread in <https://github.com/PrefectHQ/prefect/pull/6340>
- Resolved issues with capture of user-raised timeouts in <https://github.com/PrefectHQ/prefect/pull/6357>
- Added base class and async compatibility to DockerRegistry in <https://github.com/PrefectHQ/prefect/pull/6328>
- Added `max_depth` to `visit_collection`, allowing recursion to be limited in <https://github.com/PrefectHQ/prefect/pull/6367>
- Added CLI commands for inspecting and deleting Blocks and Block Types in <https://github.com/PrefectHQ/prefect/pull/6422>
- Added a Server Message Block (SMB) file system block in <https://github.com/PrefectHQ/prefect/pull/6344> — Special thanks to @darrida for this contribution!
- Removed explicit type validation from some API routes in <https://github.com/PrefectHQ/prefect/pull/6448>
- Improved robustness of streaming output from subprocesses in <https://github.com/PrefectHQ/prefect/pull/6445>
- Added a default work queue ("default") when creating new deployments from the Python client or CLI in <https://github.com/PrefectHQ/prefect/pull/6458>

### New Collections

- [prefect-monday](https://prefecthq.github.io/prefect-monday/)
- [prefect-databricks](https://prefecthq.github.io/prefect-databricks/)
- [prefect-fugue](https://github.com/fugue-project/prefect-fugue/)

**Full Changelog**: <https://github.com/PrefectHQ/prefect/compare/2.0.4...2.1.0>

## 2.0.4

### Simplified deployments

The deployment experience has been refined to remove extraneous artifacts and make configuration even easier. In particular:

- `prefect deployment build` no longer generates a  `manifest.json` file. Instead, all of the relevant information is written to the `deployment.yaml` file.
- Values in the `deployment.yaml` file are more atomic and explicit
- Local file system blocks are no longer saved automatically
- Infrastructure block values can now be overwritten with the new `infra_overrides` field

### Start custom flow runs from the UI

Now, from the deployment page, in addition to triggering an immediate flow run with default parameter arguments, you can also create a custom run. A custom run enables you to configure the run's parameter arguments, start time, name, and more, all while otherwise using the same deployment configuration. The deployment itself will be unchanged and continue to generate runs on its regular schedule.

### Improvements and bug fixes

- Made timeout errors messages on state changes more intuitive
- Added debug level logs for task run rehydration
- Added basic CLI functionality to inspect Blocks; more to come
- Added support for filtering on state name to `prefect flow-run ls`
- Refined autogenerated database migration output

## 2.0.3

This release contains a number of bug fixes and documentation improvements.

### Introducing [`prefect-dbt`](https://prefecthq.github.io/prefect-dbt/)

We've released `prefect-dbt` — a collection of Prefect integrations for working with dbt in your Prefect flows. This collection has been built as part of a partnership with dbt Labs to ensure that it follows best practices for working with dbt.

### Improvements and bug fixes

- Azure storage blocks can use `.prefectignore`
- Resolved bugs and improved interface in the Orion client.
- Resolved a bug in Azure storage blocks that would cause uploads to get stuck.
- Resolved a bug where calling a flow in a separate thread would raise an exception.
- Resolved issues with loading flows from a deployment.
- Corrected some erroneous type annotations.
- Better handling of database errors during state transition validation.
- Better sanitization of labels for Kubernetes Jobs.
- Fixes `--manifest-only` flag of `prefect deployment build` command to ensure that using this flag, the manifest gets generated, but the upload to a storage location is skipped.
- Added support for multiple YAML deployment paths to the `prefect deployment apply` command.

## 2.0.2

This release implements a number of improvements and bug fixes in response to continued engagement by members of our community. Thanks, as always, to all who submitted ideas on how to make Prefect 2 even better.

### Introducing .prefectignore files

 .prefectignore files allow users to omit certain files or directories from their deployments. Similar to other .ignore files, the syntax supports pattern matching, so an entry of `*.pyc` will ensure _all_ .pyc files are ignored by the deployment call when uploading to remote storage. Prefect provides a default .prefectignore file, but users can customize it to their needs.

### Improvements and bug fixes

- Users can now leverage Azure storage blocks.
- Users can now submit bug reports and feature enhancements using our issue templates.
- Block deletion is now more performant.
- Inconsistencies in UI button copy have been removed.
- Error messaging is clearer in the `deployment build` CLI command.
- Resolved timeout errors that occurred when using async task functions inside synchronous flows.

## 2.0.1

The response to Prefect 2 has been overwhelming in the best way possible. Thank you to the many community members who tried it out and gave us feedback! Thanks in particular to the students at this week's Prefect Associate Certification Course (PACC) in San Jose for their thoughtful recommendations. This release is a compilation of enhancements and fixes that make for a more resilient, performant, and refined Prefect experience.

### Improvements and bug fixes

- Schedules set via the API or UI are now preserved when building deployments from the CLI
- JSON types are now coerced to none, following Javascript convention and supporting standards compatibility
- The `prefect deployment execute` command has been removed to avoid confusion between running a flow locally from a Python script and running it by an agent using `prefect deployment run`
- This repository now includes templates for pull requests and issues to make bug reports and community contributions easier
- The `scheduler` and `flow-run-notifications` LoopServices have been made more resilient
- Log inserts have been made more performant through smaller log batches
- Local file system blocks created from the UI now point to the right `base_path`
- Support for unmapped values to Task.map has been added as requested by Club42 members
- The `deployment build` command now supports an optional output flag to customize the name of the deployment.yaml file, to better support projects with multiple flows

## 2.0.0

We're thrilled to announce that, with this release, Prefect 2.0 has exited its public beta! Hopefully, this release comes as no surprise. It is the culmination of nearly a year of building in public and incorporating your feedback. Prefect 2.0 is now the default version of the open source `prefect` framework provided [upon installation](https://docs.prefect.io/getting-started/installation/). We will continue enhancing Prefect 2.0 rapidly, but future breaking changes will be less frequent and more notice will be provided.

Prefect 2.0 documentation is now hosted at [docs.prefect.io](https://docs.prefect.io). Prefect 1.0 documentation is now hosted at [docs-v1.prefect.io](https://docs-v1.prefect.io).

### Upgrading from Prefect 1.0

Flows written with Prefect 1.0 will require modifications to run with Prefect 2.0. If you're using Prefect 1.0, please see our [guidance on Discourse for explicitly pinning your Prefect version in your package manager and Docker](https://discourse.prefect.io/t/the-general-availability-release-of-prefect-2-0-going-live-on-wednesday-27th-of-july-may-break-your-flows-unless-you-take-action-as-soon-as-possible/1227), so that you can make the transition to Prefect 2.0 when the time is right for you. See our [migration page](https://upgrade.prefect.io/) to learn more about upgrading.

### Upgrading from earlier versions of Prefect 2.0

We have shipped a lot of breaking changes to Prefect 2.0 over the past week. Most importantly, **recent changes to deployments required that schedules for all previously created deployments be turned off**. You can learn more about the changes via the [deployments concept documentation](https://docs.prefect.io/concepts/deployments/), the [tutorial](https://docs.prefect.io/tutorials/deployments/), or the [discourse guide](https://discourse.prefect.io/t/deployments-are-now-simpler-and-declarative/1255).

## 2.0b16

### Simplified, declarative deployments

Prefect 2.0's deployments are a powerful way to encapsulate a flow, its required infrastructure, its schedule, its parameters, and more. Now, you can create deployments simply, with just two commands:

1. `prefect deployment build ./path/to/flow/file.py:name_of_flow_obj --name "Deployment Name"` produces two files:
     — A manifest file, containing workflow-specific information such as the code location, the name of the entrypoint flow, and flow parameters
     — A `deployment.yaml` file — a complete specification of the metadata and configuration for the deployment such as the name, tags, and description
3. `prefect deployment apply ./deployment.yaml` creates or updates a deployment with the Orion server

Once the deployment is created with the Orion server, it can now be edited via the UI! See the [Deployments documentation to learn more](https://orion-docs.prefect.io/concepts/deployments/).

### Improvements and bug fixes

- The [Dask and Ray tutorials](https://orion-docs.prefect.io/tutorials/dask-ray-task-runners/) have been updated to reflect recent changes
- The [Blocks concept doc](https://orion-docs.prefect.io/concepts/blocks/) has been updated to reflect recent enhancements and includes additional examples
- The [Storage concept doc](https://orion-docs.prefect.io/concepts/storage/) has been updated to reflect recent enhancements
- All IntervalSchedules now require both an anchor date and a timezone
- The new S3 file system block enables you to read and write data as a file on Amazon S3
- The new GCS file system block allows you to read and write data as a file on Google Cloud Storage

## 2.0b15

### Uniquely refer to blocks with slugs

Blocks are a convenient way to secure store and retrieve configuration. Now, retrieving configuration stored with blocks is even easier with slugs, both human and machine readable unique identifiers. By default, block type slugs are a lowercase, dash delimited version of the block type name, but can be customized via the `_block_type_slug` field on a custom Block subclass. Block document slugs are a concatenation of [block-type-slug]/[block-document-name] and can be used as an argument to the `Block.load` method. Slugs and block document names may only include alphanumeric characters and dashes.

**Warning**: This breaking change makes this release incompatible with previous versions of the Orion server and Prefect Cloud 2.0

### Other improvements and bug fixes

## 2.0b14

### Retrieve the state of your tasks or flows with the `return_state` kwarg

Beginning with 2.0b9, Prefect 2.0 began returning function results, instead of Prefect futures and states, by default. States are still an important concept in Prefect 2. They can be used to dictate and understand the behavior of your flows. Now, you can access the state for _any_ task or flow with the new `return_state` kwarg. Just set `return_state=True` in you flow or task call and you can access its state with the `.result()` method, even if it's been submitted to a task runner.

### `prefect cloud` commands are easier to use

The `prefect cloud login` command no longer overwrites your current profile with a new API URL and auth key. Instead, the command will prompt you to create a new profile when logging into Prefect Cloud 2.0. Subsequent calls to prefect cloud login using the same key will simply "log in" to prefect cloud by switching to the profile associated with that authentication key.

The new `prefect cloud workspace ls` command lists available workspaces.

### Other improvements and bug fixes

- The anchor datetime (aka start datetime) for all newly created interval schedules will be the current date & time
- The `prefect orion start` command now handles keyboard interrupts
- CLI performance has been sped up 30-40% through improved import handling
- UI screenschots have been updated throughout the documentation
- Broken links don't feel as bad with our slick new 404 page

## 2.0b13

### Improvements and bug fixes

- RRule schedule strings are now validated on initialization to confirm that the provided RRule strings are valid
- Concepts docs have been updated for clarity and consistency
- `IntervalSchedule`'s now coerce naive datetimes to timezone-aware datetimes, so that interval schedules created with timezone-unaware datetimes will work

## 2.0b12

### Work queue pages now display upcoming runs

A new "Upcoming runs" tab has been added to the work queue page, enabling you to see all of the runs that are eligible for that work queue before they are picked up by an agent.

### Other improvements and bug fixes

- You can now set a concurrency limit when creating a work queue via the CLI
- In order to avoid unwittingly breaking references to shared blocks, block names are no longer editable
- Getting started documentation has been updated and edited for clarity
- Blocks API documentation has been updated to include system, kubernetes, and notifications block modules

## 2.0b11

This release builds upon the collection of small enhancements made in the previous release.

### Default storage has been removed

For convenience, earlier versions of Prefect 2.0 allowed for a global storage setting. With forthcoming enhancements to blocks, this will no longer be necessary.

### Other improvements and bug fixes

- We have published a [guide for migrating workflows from Prefect 1.0 (and lower) to Prefect 2.0](https://orion-docs.prefect.io/migration_guide/)
- The Flow run page now has a clearer empty state that is more consistent with other pages
- Tutorial documentation has been further updated to reflect new result behavior
- Tasks and flows now run in interruptible threads when timeouts are used
- Parameter validation no longer fails on unsupported types
- The UI now returns you to the blocks overview after deleting a block
- Flow run logs have been updated to improve user visibility into task runner usage
- Concurrency limits of 0 are now respected on work queues

## 2.0b10

This release is the first of a series of smaller releases to be released daily.

### Improvements and bug fixes

- The Blocks selection page now includes more complete and consistent metadata about each block type, including block icons, descriptions, and examples
- We've added a new [CLI style guide](https://github.com/PrefectHQ/prefect/blob/orion/docs/contributing/style.md#command-line-interface-cli-output-messages) for contributors
- Work queues no longer filter on flow runner types, this capability will instead be achieved through tags
- Tutorial documentation has been updated to reflect new result behavior

## 2.0b9

Big things are in the works for Prefect 2! This release includes breaking changes and deprecations in preparation for Prefect 2 graduating from its beta period to General Availability.

**With next week's release on July 27th, Prefect 2 will become the default package installed with `pip install prefect`. Flows written with Prefect 1 will require modifications to run with Prefect 2**. Please ensure that your package management process enables you to make the transition when the time is right for you.

### Code as workflows

As Prefect 2 usage has grown, we've observed a pattern among users, especially folks that were not previously users of Prefect 1. Working with Prefect was so much like working in native Python, users were often surprised that their tasks returned futures and states, Prefect objects, rather than results, the data that their Python functions were handling. This led to unfamiliar, potentially intimidating, errors in some cases. With this release, Prefect moves one step closer to code as workflows — tasks now return the results of their functions, rather than their states, by default. This means that you can truly take most native Python scripts, add the relevant @flow and @task decorators, and start running that script as a flow, benefitting from the observability and resilience that Prefect provides.

States and futures are still important concepts in dictating and understanding the behavior of flows. You will still be able to easily access and use them with the `.submit()` method. You will need to modify tasks in existing Prefect 2 flows to use this method to continue working as before.

### Other improvements and bug fixes

- A new `Secret` block can store a string that is encrypted at rest as well as obfuscated in logs and the UI
- Date filters on the flow run page in the UI now support filtering by date _and_ time
- Each work queue page in the UI now includes a command to start a corresponding agent
- Tutorials have been updated for increased clarity and consistency
- Cron schedule setting errors are now more informative
- Prefect now still works even if the active profile is missing
- Conda requirements regex now supports underscores and dots
- The previously deprecated `DeploymentSpec` has been removed

## 2.0b8

This is our biggest release yet! It's full of exciting new features and refinements to existing concepts. Some of these features are the result of careful planning and execution over the past few months, while others are responses to your feedback, unplanned but carefully considered. None would be possible without your continued support. Take it for a spin and let us know what you think!

This release removes the deprecated `DaskTaskRunner` and `RayTaskRunner` from the core library, breaking existing references to them. You can find them in their respective collections [prefect-ray](https://prefecthq.github.io/prefect-ray/) and [prefect-dask](https://prefecthq.github.io/prefect-dask). It also removes the previously deprecated restart policy for the `KubernetesFlowRunnner`. Most importantly, there are new **breaking changes** to the Deployments interface described below.

### Flow Run Retries

Flow run retries have been one of our most requested features, especially given how easy it is to run a flow as a "subflow" or "child flow" with Prefect 2.0. Flow run retries are configured just as task retries are — with the `retries` and `retry_delay_seconds` parameters.

If both a task and its flow have retries configured, tasks within the flow will retry up to their specified task retry limit for each flow run. For example, if you have a **flow** configured with a limit of 2 retries (up to 3 total runs, including the initial attempt), and a **task** in the flow configured with 3 retries (up to 4 attempts per flow run, including the initial attempt). The task could run up to a total of 12 attempts, since task retry limits are reset after each flow run or flow run attempt.

### Notifications

At any time, you can visit the Prefect UI to get a comprehensive view of the state of all of your flows, but when something goes wrong with one of them, you need that information immediately. Prefect 2.0’s new notifications can alert you and your team when any flow enters any state you specify, with or without specific tags.

To create a notification, go to the new Notifications page via the sidebar navigation and select “Create Notification.” Notifications are structured just as you would describe them to someone. For example, if I want to get a Slack message every time my daily-ETL flow fails, my notification will simply read:

> If a run of any flow with **any** tag enters a **failed** state, send a notification to **my-slack-webhook**

When the conditions of the notification are triggered, you’ll receive a simple message:

> The **fuzzy-leopard** run of the **daily-etl** flow entered a **failed** state at **yy-MM-dd HH:mm:ss TMZ**.

Currently, notifications can only be sent to a [Slack webhook](https://api.slack.com/messaging/webhooks) (or email addresses if you are using [Prefect Cloud 2.0](https://app.prefect.cloud)). Over time, notifications will support additional messaging services. Let us know which messaging services you’d like to send your notifications to!

### Flow packaging and deployment

We've revisited our flow packaging and deployment UX, making it both more powerful and easier to use. `DeploymentSpec`s are now just `Deployment`s. Most of the fields are unchanged, but there are a few differences:

- The `flow_storage` field has been replaced with a `packager` field.
- The `flow_location`, `flow_name`, and `flow` parameters are now just `flow`.

We now support customization of the deployment of your flow. Previously, we just uploaded the source code of the flow to a file. Now, we've designed a packaging systems which allows you to control how and where your flow is deployed. We're including three packagers in this release:

- `OrionPackager`: Serializes the flow and stores it in the Orion database, allowing you to get started without setting up remote storage.
- `FilePackager`: Serializes the flow and stores it in a file. The core library supports local and remote filesystems. Additional remote file systems will be available in collections.
- `DockerPackager`: Copies the flow into a new Docker image. You can take full control of the Docker image build or use Prefect to detect your current Python dependencies and install them in the image.

For packagers that support it, three serializers are available as well:

- `ImportSerializer`: Serializes to the import path of the flow. The flow will need to be importable at runtime.
- `SourceSerializer`: Serializes to the source code of the flow's module.
- `PickleSerializer`: Serializes the flow using cloudpickle with support for serialization full modules.

Learn more in the [Deployment concept documentation](https://docs.prefect.io/concepts/deployments/).

You can continue to use your existing `DeploymentSpec`s, but they are deprecated and will be removed in the coming weeks.

### Blocks

We've been working on Blocks behind the scenes for a while. Whether you know it or not, if you've used the past few releases, you've used them. Blocks enable you to securely store configuration with the Prefect Orion server and access it from your code later with just a simple reference. Think of Blocks as secure, UI-editable, type-checked environment variables. We're starting with just a few Blocks — mostly storage, but over time we’ll expand this pattern to include every tool and service in the growing modern data stack. You'll be able to set up access to your entire stack once in just a few minutes, then manage access forever without editing your code. In particular, we've made the following enhancements:

- Block document values can now be updated via the Python client with the `overwrite` flag.
- Blocks now support secret fields. By default, fields identified as secret will be obfuscated when returned to the Prefect UI. The actual values can still be retrieved as necessary.
- `BlockSchema` objects have a new `secret_fields: List[str]` item in their schema's extra fields. This is a list of all fields that should be considered "secret". It also includes any secret fields from nested blocks referenced by the schema.
- You can now browse your Blocks on the new "Blocks" page, create, and edit them right in the UI.

### Other Improvements

- Task keys, previously a concatenation of several pieces of metadata, are now only the qualified function name. While it is likely to be globally unique, the key can be used to easily identify every instance in which a function of the same name is utilized.
- Tasks now have a `version` that you can set via the task decorator, like the flow version identifier on flow runs.
- An Orion setting, `PREFECT_ORION_DATABASE_PASSWORD`, has been added to allow templating in the database connection URL
- A link to API reference documentation has been added to the Orion startup message.
- Where possible, Prefect 2.0 now exits processes earlier for synchronous flow or task runs that are cancelled. This reduces the range of conditions under which a task run would be marked failed, but continue to run.
- All Prefect client models now allow extras, while the API continues to forbid them, such that older Prefect 2.0 clients can receive and load objects from the API that have additional fields, facilitating backwards compatibility.
- The _all_ attribute has been added to **init**.py for all public modules, declaring the public API for export.
- A new endpoint, `/deployments/{id}/work_queue_check`, enables you to to check which work queues the scheduled runs of a deployment will be eligible for.

### Bug fixes

- Attempting to create a schedule with a cron string that includes a "random" or "hashed" expression will now return an error.

### Contributors

- [Cole Murray](https://github.com/ColeMurray)
- [Oliver Mannion](https://github.com/tekumara)
- [Steve Flitcroft](https://github.com/redsquare)
- [Laerte Pereira](https://github.com/Laerte)

## 2.0b7

This release includes a number of important improvements and bug fixes in response to continued feedback from the community. Note that this release makes a **breaking change** to the Blocks API, making the `2.0b7` Orion server incompatible with previous Orion client versions.```

### Improvements

- Added the color select to the Orion UI in OSS (enabling users to change their state color scheme) for the UI.
- Added anonymous blocks, allowing Prefect to dynamically store blocks for you without cluttering your workspace.
- Performance improvements to the service that marks flows runs as late.
- Added the ability for flow names to include underscores for use in DeploymentSpecs.
- Split [Ray](https://prefecthq.github.io/prefect-ray/) and [Dask](https://prefecthq.github.io/prefect-dask/) task runners into their own collections.
- Removed delays to agent shutdown on keyboard interrupt.
- Added informative messaging when an agent is reading from a paused work queue.
- Improved task naming conventions for tasks defined using lambda functions

### Documentation improvements

- Updated screenshots and description of workflows to reflect new UI
- Revised and extended Prefect Cloud quickstart tutorial
- Added deployments page
- Added documentation for `prefect cloud workspace set` command

### Collections

- [prefect-sqlalchemy](https://prefecthq.github.io/prefect-sqlalchemy/)
- [prefect-dask](https://prefecthq.github.io/prefect-dask/)
- [prefect-ray](https://prefecthq.github.io/prefect-ray/)
- [prefect-snowflake](https://prefecthq.github.io/prefect-snowflake/)
- [prefect-openmetadata](https://prefecthq.github.io/prefect-openmetadata/)
- [prefect-airbyte](https://prefecthq.github.io/prefect-airbyte/)

Note that the Dask and Ray task runners have been moved out of the Prefect core library to reduce the number of dependencies we require for most use cases. Install from the command line with `pip install prefect-dask` and import with `from prefect_dask.task_runners import DaskTaskRunner`.

### Bug fixes

- [Allow Orion UI to run on Windows](https://github.com/PrefectHQ/prefect/pull/5802)
- Fixed a bug in terminal state data handling that caused timeouts
- Disabled flow execution during deployment creation to prevent accidental execution.
- Fixed a bug where Pydantic models being passed to Prefect tasks would drop extra keys and private attributes.
- Fixed a bug where the `KubernetesFlowRunner` was not serializable.

## 2.0b6

We're so grateful for the fountain of feedback we've received about Prefect 2. One of the themes in feedback was that Prefect 2's UI didn't reflect the same clarity and elegance that the rest of Prefect 2 did. We agreed! Today, we've proud to share Prefect 2's completely redesigned UI. It's simpler, faster, and easier to use. Give it a spin!

This release includes several other exciting changes, including:

- **Windows** support
- A new CLI command to delete flow runs: `prefect flow-run delete`
- Improved API error messages
- Support for type-checking with VS Code and other editors that look for a `py.typed` file

Here's a preview of the type hints that you'll start seeing now in editors like VS Code:

<img src="docs/img/release-notes/functionhint.png">

<img src="docs/img/release-notes/futurehint.png">

Note that this release makes a **breaking change** to the Blocks API, making the `2.0b6` Orion server incompatible with previous Orion client versions. You may not be familiar with Blocks, but it's likely that you have already used one in the `flow_storage` part of your `DeploymentSpec`. This change is foundational for powerful new features we're working on for upcoming releases. Blocks will make all sorts of exciting new use cases possible.

After the upgrade your data will remain intact, but you will need to upgrade to `2.0b6` to continue using the Cloud 2.0 API. You can upgrade in just a few simple steps:

- Install the latest Prefect 2.0 python package: `pip install -U "prefect>=2.0b6"`
- Restart any existing agent processes
  - If you are using an agent running on Kubernetes, update the Prefect image version to `2.0b6` in your Kubernetes manifest and re-apply the deployment.
  - You don't need to recreate any deployments or pause any schedules — stopping your agent process to perform an upgrade may result in some Late Runs, but those will be picked up once you restart your agent.

## 2.0b5

This release includes some small improvements that we want to deliver immediately instead of bundling them with the next big release.

The `prefect.testing` module is now correctly included in the package on PyPI.

The Prefect UI no longer uses a hard-coded API URL pointing at `localhost`. Instead, the URL is pulled from the `PREFECT_ORION_UI_API_URL` setting. This setting defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from `PREFECT_ORION_API_HOST` and `PREFECT_ORION_API_PORT`. If providing a custom value, the aforementioned settings may be templated into the given string.

## 2.0b4

We're really busy over here at Prefect! We've been getting great feedback from early adopters. There's a lot of work going on behind the scenes as we work on building some exciting new features that will be exclusive to Prefect 2.0, but we want to keep the enhancements flowing to you. In that spirit, there are a lot of quality-of-life improvements here!

While most of the development of Prefect 2.0 is still happening internally, we're incredibly excited to be getting contributions in our open source repository. Big shoutout to our contributors for this last release:

- @dannysepler
- @ColeMurray
- @albarrentine
- @mkarbo
- @AlessandroLollo

### Flow and task runners

- Flow runners now pass all altered settings to their jobs instead of just the API key and URL
- The Kubernetes flow runner supports configuration of a service account name
- The subprocess flow runner streams output by default to match the other flow runners
- The Dask task runner has improved display of task keys in the Dask dashboard
- The Dask task runner now submits the execution graph to Dask allowing optimization by the Dask scheduler

Note that the Dask and Ray task runners will be moving out of the core Prefect library into dedicated `prefect-ray` and `prefect-dask` collections with the next release. This will reduce the number of dependencies we require for most use cases. Since we now have concurrent execution built in to the core library, these packages do not need to be bundled with Prefect. We're looking forward to building additional tasks and flows specific to Ray and Dask in their respective collections.

### Collections

Speaking of collections, we've received our first [user-contributed collection](https://github.com/AlessandroLollo/prefect-cubejs). It includes tasks for [Cube.js](https://cube.dev/), check it out!

The following collections have also been recently released:

- [`prefect-great-expectations`](https://github.com/PrefectHQ/prefect-great-expectations)
- [`prefect-twitter`](https://github.com/PrefectHQ/prefect-twitter)
- [`prefect-github`](https://github.com/PrefectHQ/prefect-github)

You can see a list of all available collections in the [Prefect Collections Catalog](https://docs.prefect.io/collections/catalog/).

### Windows compatibility

We've excited to announce that we've begun work on Windows compatibility. Our full test suite isn't passing yet, but we have core features working on Windows. We expect the majority of the edge cases to be addressed in an upcoming release.

### Documentation improvements

We've added some new documentation and made lots of improvements to existing documentation and tutorials:

- Added documentation for associating conda environments with separate Prefect profiles
- Added storage steps and advanced examples to the Deployments tutorial
- Expanded documentation of storage options
- Added workspace details to the Prefect Cloud documentation
- Improved schedules documentation with examples
- Revised the Kubernetes tutorial to include work queue setup
- Improved tutorial examples of task caching

### CLI

- Deployments can be deleted from the CLI
- The CLI displays help by default
- `prefect version` is robust to server connection errors
- `prefect config view` shows sources by default
- `prefect deployment create` exits with a non-zero exit code if one of the deployments fails to be created
- `prefect config set` allows setting values that contain equal signs
- `prefect config set` validates setting types before saving them
- `prefect profile inpect` displays settings in a profile instead of duplicating prefect config view behavior
- `prefect storage create` trims long descriptions

### Bug squashing

We've eradicated some bugs, replacing them with good behavior:

- Flow runs are now robust to log worker failure
- Deployment creation is now robust to `ObjectAlreadyExists` errors
- Futures from async tasks in sync flows are now marked as synchronous
- Tildes (~) in user-provided paths for `PREFECT_HOME` are expanded
- Fixed parsing of deployments defined in YAML
- Deployment deletion cleans up scheduled runs

### Optimizations and refactors

You might not see these fixes in your day-to-day, but we're dedicated to improving performance and maintaining our reputation as maintainers of an approachable and clean project.

- The `state_name` is attached to run models for improved query performance
- Lifespan management for the ephemeral Orion application is now robust to deadlocks
- The `hello` route has moved out of the `admin` namespace so it is available on Prefect Cloud
- Improved readability and performance of profile management code
- Improved lower-bounds dependency parsing
- Tests are better isolated and will not run against a remote API
- Improved representation of Prefect `Setting` objects
- Added extensive tests for `prefect config` and `prefect profile` commands
- Moved testing utilities and fixtures to the core library for consumption by collections

## 2.0b3

### Improvements

- Improved filter expression display and syntax in the UI.
- Flow runs can be queried more flexibly and performantly.
- Improved results persistence handling.
- Adds code examples to schedules documentation.
- Added a unit testing utility, `prefect_test_harness`.
- Various documentation updates.

### Bug fixes

- The Scheduler no longer crashes on misconfigured schedules.
- The MarkLateRuns service no longer marks runs as `Late` several seconds too early.
- Dashboard filters including flow/task run states can now be saved.
- Flow runs can no longer transition from terminal states. The engine will no longer try to set the final state of a flow run twice.
- Scheduled flow runs are now deleted when their corresponding deployment is deleted.
- Work queues created in the UI now work the same as those created with the CLI.
- Kubernetes flow runners now correctly inject credentials into the execution environment.
- Work queues created via the UI now function correctly.

## 2.0b2

### Improvements

- Docker flow runners can connect to local API applications on Linux without binding to `0.0.0.0`.
- Adds `with_options` method to flows allowing override of settings e.g. the task runner.

### Bug fixes

- The CLI no longer displays tracebacks on successful exit.
- Returning pandas objects from tasks does not error.
- Flows are listed correctly in the UI dashboard.

## 2.0b1

We are excited to introduce this branch as [Prefect 2.0](https://www.prefect.io/blog/introducing-prefect-2-0/), powered by [Orion, our second-generation orchestration engine](https://www.prefect.io/blog/announcing-prefect-orion/)! We will continue to develop Prefect 2.0 on this branch. Both the Orion engine and Prefect 2.0 as a whole will remain under active development in beta for the next several months, with a number of major features yet to come.

This is the first release that's compatible with Prefect Cloud 2.0's beta API — more exciting news to come on that soon!

### Expanded UI

Through our technical preview phase, our focus has been on establishing the right [concepts](https://docs.prefect.io/concepts/overview/) and making them accessible through the CLI and API. Now that some of those concepts have matured, we've made them more accessible and tangible through UI representations. This release adds some very important concepts to the UI:

**Flows and deployments**

If you've ever created a deployment without a schedule, you know it can be difficult to find that deployment in the UI. This release gives flows and their deployments a dedicated home on the growing left sidebar navigation. The dashboard continues to be the primary interface for exploring flow runs and their task runs.

**Work queues**

With the [2.0a13 release](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md#work-queues), we introduced [work queues](https://docs.prefect.io/concepts/work-queues/), which could only be created through the CLI. Now, you can create and edit work queues directly from the UI, then copy, paste, and run a command that starts an agent that pulls work from that queue.

### Collections

Prefect Collections are groupings of pre-built tasks and flows used to quickly build data flows with Prefect.

Collections are grouped around the services with which they interact. For example, to download data from an S3 bucket, you could use the `s3_download` task from the [prefect-aws collection](https://github.com/PrefectHQ/prefect-aws), or if you want to send a Slack message as part of your flow you could use the `send_message` task from the [prefect-slack collection](https://github.com/PrefectHQ/prefect-slack).

By using Prefect Collections, you can reduce the amount of boilerplate code that you need to write for interacting with common services, and focus on the outcome you're seeking to achieve. Learn more about them in [the docs](https://docs.prefect.io/collections/catalog.md).

### Profile switching

We've added the `prefect profile use <name>` command to allow you to easily switch your active profile.

The format for the profiles file has changed to support this. Existing profiles will not work unless their keys are updated.

For example, the profile "foo" must be changed to "profiles.foo" in the file `profiles.toml`:

```toml
[foo]
SETTING = "VALUE"
```

to

```toml
[profiles.foo]
SETTING = "VALUE"
```

### Other enhancements

- It's now much easier to explore Prefect 2.0's major entities, including flows, deployments, flow runs, etc. through the CLI with the `ls` command, which produces consistent, beautifully stylized tables for each entity.
- Improved error handling for issues that the client commonly encounters, such as network errors, slow API requests, etc.
- The UI has been polished throughout to be sleeker, faster, and even more intuitive.
- We've made it even easier to access file storage through [fsspec](https://filesystem-spec.readthedocs.io/en/latest/index.html), which includes [many useful built in implementations](https://filesystem-spec.readthedocs.io/en/latest/api.html#built-in-implementations).

## 2.0a13

We've got some exciting changes to cover in our biggest release yet!

### Work queues

Work queues aggregate work to be done and agents poll a specific work queue for new work. Previously, agents would poll for any scheduled flow run. Now, scheduled flow runs are added to work queues that can filter flow runs by tags, deployment, and flow runner type.

Work queues enable some exiting new features:

- Filtering: Each work queue can target a specific subset of work. This filtering can be adjusted without restarting your agent.
- Concurrency limits: Each work queue can limit the number of flows that run at the same time.
- Pausing: Each work queue can be paused independently. This prevents agents from submitting additional work.

Check out the [work queue documentation](https://docs.prefect.io/concepts/work-queues/) for more details.

Note, `prefect agent start` now requires you to pass a work queue identifier and `prefect orion start` no longer starts an agent by default.

### Remote storage

Prior to this release, the Orion server would store your flow code and results in its local file system. Now, we've introduced storage with external providers including AWS S3, Google Cloud Storage, and Azure Blob Storage.

There's an interactive command, `prefect storage create`, which walks you through the options required to configure storage. Your settings are encrypted and stored in the Orion database.

Note that you will no longer be able to use the Kubernetes or Docker flow runners without configuring storage. While automatically storing flow code in the API was convenient for early development, we're focused on enabling the [hybrid model](https://www.prefect.io/why-prefect/hybrid-model/) as a core feature of Orion.

### Running tasks on Ray

We're excited to announce a new task runner with support for [Ray](https://www.ray.io/). You can run your tasks on an existing Ray cluster, or dynamically create one with each flow run. Ray has powerful support for customizing runtime environments, parallelizing tasks to make use of your full compute power, and dynamically creating distributed task infrastructure.

An [overview of using Ray](https://docs.prefect.io/concepts/task-runners/#running-tasks-on-ray) can be found in our documentation.

### Profiles

Prefect now supports profiles for configuration. You can store settings in profiles and switch between them. For example, this allows you to quickly switch between using a local and hosted API.

View all of the available commands with `prefect config --help` and check out our [settings documentation](https://docs.prefect.io/concepts/settings/) for a full description of how to use profiles.

We've also rehauled our [settings reference](https://docs.prefect.io/api-ref/prefect/settings/#prefect.settings.Settings) to make it easier to see all the available settings. You can override any setting with an environment variable or `prefect config set`.

## 2.0a12

### Filters

Orion captures valuable metadata about your flows, deployments, and their runs. We want it to be just as simple to retrieve this information as it is to record it. This release exposes a powerful set of filter operations to cut through this body of information with ease and precision. Want to see all of the runs of your Daily ETL flow? Now it's as easy as typing `flow:"Daily ETL"` into the filter bar. This update also includes a query builder UI, so you can utilize and learn these operators quickly and easily.

## 2.0a11

### Run Orion on Kubernetes

You can now can run the Orion API, UI, and agent on Kubernetes. We've included a new Prefect CLI command, `prefect kubernetes manifest orion`, that you can use to automatically generate a manifest that runs Orion as a Kubernetes deployment.

Note: Prefect 2.0 beta versions prior to 2.0b6 used the CLI command `prefect orion kubernetes-manifest`.

### Run flows on Kubernetes

With the `KubernetesJob` [infrastructure](https://orion-docs.prefect.io/concepts/infrastructure/), you can now run flows as Kubernetes Jobs. You may specify the Kubernetes flow runner when creating a deployment. If you're running Orion in Kubernetes, you don't need to configure any networking. When the agent runs your deployment, it will create a job, which will start a pod, which creates a container, which runs your flow. You can use standard Kubernetes tooling to display flow run jobs, e.g. `kubectl get jobs -l app=orion`.

## 2.0a10

### Concurrent task runner

Speed up your flow runs with the new Concurrent Task Runner. Whether your code is synchronous or asynchronous, this [task runner](https://docs.prefect.io/concepts/task-runners/) will enable tasks that are blocked on input/output to yield to other tasks. To enable this behavior, this task runner always runs synchronous tasks in a worker thread, whereas previously they would run in the main thread.

### Task run concurrency limits

When running a flow using a task runner that enables concurrent execution, or running many flows across multiple execution environments, you may want to limit the number of certain tasks that can run at the same time.

Concurrency limits are set and enforced with task run tags. For example, perhaps you want to ensure that, across all of your flows, there are no more than three open connections to your production database at once. You can do so by creating a “prod-db” tag and applying it to all of the tasks that open a connection to that database. Then, you can create a concurrency limit with `prefect concurrency-limit create prod-db 3`. Now, Orion will ensure that no more than 3 task runs with the “prod-db” tag will run at the same time. Check out [the documentation](https://docs.prefect.io/concepts/tasks/) for more information about task run concurrency limits and other task level concepts.

This feature was previously only available in a paid tier of Prefect Cloud, our hosted commercial offering. We’re very happy to move it to the open source domain, furthering our goal of making Orion the most capable workflow orchestration tool ever.

### Flow parameters

Previously, when calling a flow, we required passed arguments to be serializable data types. Now, flows will accept arbitrary types, allowing ad hoc flow runs and subflow runs to consume unserializable data types. This change is motivated by two important use-cases:

- The flow decorator can be added to a wider range of existing Python functions
- Results from tasks can be passed directly into subflows without worrying about types

Setting flow parameters via the API still requires serializable data so we can store your new value for the parameter. However, we support automatic deserialization of those parameters via type hints. See the [parameters documentation](https://docs.prefect.io/concepts/flows/#parameters) for more details.

### Database migrations

The run metadata that Orion stores in its database is a valuable record of what happened and why. With new database migrations for both SQLite and PostgreSQL, you can retain your data when upgrading. The CLI interface has been updated to include new commands and revise an existing command to leverage these migrations:

- `prefect orion reset-db` is now `prefect orion database reset`
- `prefect orion database upgrade` runs upgrade migrations
- `prefect orion database downgrade` runs downgrade migrations

**Breaking Change**
Because these migrations were not in place initially, if you have installed any previous version of Orion, you must first delete or stamp the existing database with `rm ~/.prefect/orion.db` or `prefect orion database stamp`, respectively. Learn more about database migrations in [the documentation](https://docs.prefect.io/tutorials/orchestration/#the-database).

### CLI refinements

The CLI has gotten some love with miscellaneous additions and refinements:

- Added `prefect --version` and `prefect -v` to expose version info
- Updated `prefect` to display `prefect --help`
- Enhanced `prefect dev` commands:
    — Added `prefect dev container` to start a container with local code mounted
    — Added `prefect dev build-image` to build a development image
    — Updated `prefect dev start` to hot-reload on API and agent code changes
    — Added `prefect dev api` and `prefect dev agent` to launch hot-reloading services individually

### Other enhancements

- Feel the thrill when you start Orion or an agent with our new banners
- Added a new logging setting for the Orion server log level, defaulting to "WARNING", separate from the client logging setting
- Added a method, `with_options`, to the `Task` class. With this method, you can easily create a new task with modified settings based on an existing task. This will be especially useful in creating tasks from a prebuilt collection, such as Prefect’s task library.
- The logs tab is now the default tab on flow run page, and has been refined with usability and aesthetic improvements.
- As Orion becomes more capable of distributed deployments, the risk of client/server incompatibility issues increases. We’ve added a guard against these issues with API version checking for every request. If the version is missing from the request header, the server will attempt to handle it. If the version is incompatible with the Orion server version, the server will reject it.

## 2.0a9

### Logs

This release marks another major milestone on Orion's continued evolution into a production ready tool. Logs are fundamental output of any orchestrator. Orion's logs are designed to work exactly the way that you'd expect them to work. Our logger is built entirely on Python's [standard library logging configuration hooks](https://docs.python.org/3/library/logging.config.html), so you can easily output to JSON, write to files, set levels, and more — without Orion getting in the way. All logs are associated with a flow run ID. Where relevant, they are also associated with a task run ID.

Once you've run your flow, you can find the logs in a dedicated tab on the flow run page, where you can copy them all or one line at a time. You can even watch them come in as your flow run executes. Future releases will enable further filter options and log downloads.
Learn more about logging in [the docs](https://docs.prefect.io/concepts/logs/).

### Other Enhancements

In addition to logs, we also included the scheduler in the set of services started with `prefect orion start`. Previously, this required a dedicated flag or an additional command. Now, the scheduler is always available while Orion is running.

## 2.0a8

The 2.0a7 release required users to pull Docker images (e.g. `docker pull prefecthq/prefect:2.0a7-python3.8`) before the agent could run flows in Docker.

This release adds pull policies to the `DockerFlowRunner` allowing full control over when your images should be pulled from a registry. We infer reasonable defaults from the tag of your image, following the behavior of [Kubernetes image pull policies](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy).

## 2.0a7

### Flow Runners

On the heels of the recent rename of Onion's `Executor` to `TaskRunner`, this release introduces `FlowRunner`, an analogous concept that specifies the infrastructure that a flow runs on. Just as a task runner can be specified for a flow, which encapsulates tasks, a flow runner can be specified for a deployment, which encapsulates a flow. This release includes two flow runners, which we expect to be the most commonly used:

- **SubprocessFlowRunner** — The subprocess flow runner is the default flow runner. It allows for specification of a runtime Python environment with `virtualenv` and `conda` support.
- **DockerFlowRunner** — Executes the flow run in a Docker container. The image, volumes, labels, and networks can be customized. From this release on, Docker images for use with this flow runner will be published with each release.

Future releases will introduce runners for executing flows on Kubernetes and major cloud platform's container compute services (e.g. AWS ECS, Google Cloud Run).

### Other enhancements

In addition to flow runners, we added several other enhancements and resolved a few issues, including:

- Corrected git installation command in docs
- Refined UI through color, spacing, and alignment updates
- Resolved memory leak issues associated with the cache of session factories
- Improved agent locking of double submitted flow runs and handling for failed flow run submission

## 2.0a6

### Subflows and Radar follow up

With the 2.0a5 release, we introduced the ability to navigate seamlessly between subflows and parent flows via Radar. In this release, we further enabled that ability by:

- Enabling the dedicated subflow runs tab on the Flow Run page
- Tracking of upstream inputs to subflow runs
- Adding a flow and task run count to all subflow run cards in the Radar view
- Adding a mini Radar view on the Flow run page

### Task Runners

Previous versions of Prefect could only trigger execution of code defined within tasks. Orion can trigger execution of significant code that can be run _outside of tasks_. In order to make the role previously played by Prefect's `Executor` more explicit, we have renamed `Executor` to `TaskRunner`.

A related `FlowRunner` component is forthcoming.

### Other enhancements

In addition to task runners and subflow UI enhancements, we added several other enhancements and resolved a few issues, including:

- Introduced dependency injection pathways so that Orion's database access can be modified after import time
- Enabled the ability to copy the run ID from the flow run page
- Added additional metadata to the flow run page details panel
- Enabled and refined dashboard filters to improve usability, reactivity, and aesthetics
- Added a button to remove filters that prevent deployments without runs from displaying in the dashboard
- Implemented response scoped dependency handling to ensure that a session is always committed before a response is returned to the user

## 2.0a5

### Radar: A new way of visualizing workflows

Orion can orchestrate dynamic, DAG-free workflows. Task execution paths may not be known to Orion prior to a run—the graph “unfolds” as execution proceeds. Radar embraces this dynamism, giving users the clearest possible view of their workflows.

Orion’s Radar is based on a structured, radial canvas upon which tasks are rendered as they are orchestrated. The algorithm optimizes readability through consistent node placement and minimal edge crossings. Users can zoom and pan across the canvas to discover and inspect tasks of interest. The mini-map, edge tracing, and node selection tools make workflow inspection a breeze. Radar also supports direct click-through to a subflow from its parent, enabling users to move seamlessly between task execution graphs.

### Other enhancements

While our focus was on Radar, we also made several other material improvements to Orion, including:

- Added popovers to dashboard charts, so you can see the specific data that comprises each visualization
- Refactored the `OrionAgent` as a fully client side construct
- Enabled custom policies through dependency injection at runtime into Orion via context managers

## 2.0a4

We're excited to announce the fourth alpha release of Prefect's second-generation workflow engine.

In this release, the highlight is executors. Executors are used to run tasks in Prefect workflows.
In Orion, you can write a flow that contains no tasks.
It can call many functions and execute arbitrary Python, but it will all happen sequentially and on a single machine.
Tasks allow you to track and orchestrate discrete chunks of your workflow while enabling powerful execution patterns.

[Executors](https://docs.prefect.io/concepts/executors/) are the key building blocks that enable you to execute code in parallel, on other machines, or with other engines.

### Dask integration

Those of you already familiar with Prefect have likely used our Dask executor.
The first release of Orion came with a Dask executor that could run simple local clusters.
This allowed tasks to run in parallel, but did not expose the full power of Dask.
In this release of Orion, we've reached feature parity with the existing Dask executor.
You can [create customizable temporary clusters](https://docs.prefect.io/tutorials/dask-task-runner/) and [connect to existing Dask clusters](https://docs.prefect.io/tutorials/dask-task-runner/).
Additionally, because flows are not statically registered, we're able to easily expose Dask annotations, which allow you to [specify fine-grained controls over the scheduling of your tasks](https://docs.prefect.io/tutorials/dask-task-runner/) within Dask.

### Subflow executors

[Subflow runs](https://docs.prefect.io/concepts/flows/#composing-flows) are a first-class concept in Orion and this enables new execution patterns.
For example, consider a flow where most of the tasks can run locally, but for some subset of computationally intensive tasks you need more resources.
You can move your computationally intensive tasks into their own flow, which uses a `DaskExecutor` to spin up a temporary Dask cluster in the cloud provider of your choice.
Next, you simply call the flow that uses a `DaskExecutor` from your other, parent flow.
This pattern can be nested or reused multiple times, enabling groups of tasks to use the executor that makes sense for their workload.

Check out our [multiple executor documentation](https://docs.prefect.io/concepts/executors/#using-multiple-task-runners) for an example.

### Other enhancements

While we're excited to talk about these new features, we're always hard at work fixing bugs and improving performance. This release also includes:

- Updates to database engine disposal to support large, ephemeral server flow runs
- Improvements and additions to the `flow-run` and `deployment` command-line interfaces
    — `prefect deployment ls`
    — `prefect deployment inspect <name>`
    — `prefect flow-run inspect <id>`
    — `prefect flow-run ls`
- Clarification of existing documentation and additional new documentation
- Fixes for database creation and startup issues
