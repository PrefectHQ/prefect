# Integrating shell commands into your dataflow with `prefect-shell`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-shell/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-shell?color=0052FF&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-shell/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-shell?color=0052FF&labelColor=090422" /></a>
</p>

Visit the full docs [here](https://PrefectHQ.github.io/prefect-shell) to see additional examples and the API reference.

The prefect-shell collection makes it easy to execute shell commands in your Prefect flows. Check out the examples below to get started!

## Getting Started

### Integrate with Prefect flows

With prefect-shell, you can bring your trusty shell commands (and/or scripts) straight into the Prefect flow party, complete with awesome Prefect logging.

No more separate logs, just seamless integration. Let's get the shell-abration started!

```python
from prefect import flow
from datetime import datetime
from prefect_shell import ShellOperation

@flow
def download_data():
    today = datetime.today().strftime("%Y%m%d")

    # for short running operations, you can use the `run` method
    # which automatically manages the context
    ShellOperation(
        commands=[
            "mkdir -p data",
            "mkdir -p data/${today}"
        ],
        env={"today": today}
    ).run()

    # for long running operations, you can use a context manager
    with ShellOperation(
        commands=[
            "curl -O https://masie_web.apps.nsidc.org/pub/DATASETS/NOAA/G02135/north/daily/data/N_seaice_extent_daily_v3.0.csv",
        ],
        working_dir=f"data/{today}",
    ) as download_csv_operation:

        # trigger runs the process in the background
        download_csv_process = download_csv_operation.trigger()

        # then do other things here in the meantime, like download another file
        ...

        # when you're ready, wait for the process to finish
        download_csv_process.wait_for_completion()

        # if you'd like to get the output lines, you can use the `fetch_result` method
        output_lines = download_csv_process.fetch_result()

download_data()
```

Outputs:
```bash
14:48:16.550 | INFO    | prefect.engine - Created flow run 'tentacled-chachalaca' for flow 'download-data'
14:48:17.977 | INFO    | Flow run 'tentacled-chachalaca' - PID 19360 triggered with 2 commands running inside the '.' directory.
14:48:17.987 | INFO    | Flow run 'tentacled-chachalaca' - PID 19360 completed with return code 0.
14:48:17.994 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 triggered with 1 commands running inside the PosixPath('data/20230201') directory.
14:48:18.009 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dl
14:48:18.010 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
oad  Upload   Total   Spent    Left  Speed
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
14:48:18.840 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
 11 1630k   11  192k    0     0   229k      0  0:00:07 --:--:--  0:00:07  231k
14:48:19.839 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
 83 1630k   83 1368k    0     0   745k      0  0:00:02  0:00:01  0:00:01  747k
14:48:19.993 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
100 1630k  100 1630k    0     0   819k      0  0
14:48:19.994 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 stream output:
:00:01  0:00:01 --:--:--  821k
14:48:19.996 | INFO    | Flow run 'tentacled-chachalaca' - PID 19363 completed with return code 0.
14:48:19.998 | INFO    | Flow run 'tentacled-chachalaca' - Successfully closed all open processes.
14:48:20.203 | INFO    | Flow run 'tentacled-chachalaca' - Finished in state Completed()
```

!!! info "Utilize Previously Saved Blocks"

    You can save commands within a `ShellOperation` block, then reuse them across multiple flows, or even plain Python scripts.
    
    Save the block with desired commands:

    ```python
    from prefect_shell import ShellOperation

    ping_op = ShellOperation(commands=["ping -t 1 prefect.io"])
    ping_op.save("block-name")
    ```

    Load the saved block:

    ```python
    from prefect_shell import ShellOperation

    ping_op = ShellOperation.load("block-name")
    ```

    To [view and edit the blocks](https://orion-docs.prefect.io/ui/blocks/) on Prefect UI:

    ```bash
    prefect block register -m prefect_shell
    ```

## Resources

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://orion-docs.prefect.io/collections/usage/)!

### Installation

Install `prefect-shell` with `pip`:

```bash
pip install -U prefect-shell
```

A list of available blocks in `prefect-shell` and their setup instructions can be found [here](https://PrefectHQ.github.io/prefect-shell/blocks_catalog).

Requires an installation of Python 3.7+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://orion-docs.prefect.io/).

### Feedback

If you encounter any bugs while using `prefect-shell`, feel free to open an issue in the [prefect-shell](https://github.com/PrefectHQ/prefect-shell) repository.

If you have any questions or issues while using `prefect-shell`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

Feel free to star or watch [`prefect-shell`](https://github.com/PrefectHQ/prefect-shell) for updates too!
 
### Contributing
 
If you'd like to help contribute to fix an issue or add a feature to `prefect-shell`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).
 
Here are the steps:

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Insert an entry to [CHANGELOG.md](https://github.com/PrefectHQ/prefect-shell/blob/main/CHANGELOG.md)
7. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
8. `git commit`, `git push`, and create a pull request
