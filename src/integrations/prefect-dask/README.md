# `prefect-dask`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-dask/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-dask?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-dask/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-dask?color=26272B&labelColor=090422" /></a>
</p>

The `prefect-dask` collection makes it easy to include distributed processing for your flows. Check out the examples below to get started!

## Getting Started

### Integrate with Prefect flows

Perhaps you're already working with Prefect flows. Say your flow downloads many images to train your machine learning model. Unfortunately, it takes a long time to download your flows because your code is running sequentially.

After installing `prefect-dask` you can parallelize your flow in three simple steps:

1. Add the import: `from prefect_dask import DaskTaskRunner`
2. Specify the task runner in the flow decorator: `@flow(task_runner=DaskTaskRunner)`
3. Submit tasks to the flow's task runner: `a_task.submit(*args, **kwargs)`

The parallelized code  runs in about 1/3 of the time in our test!  And that's without distributing the workload over multiple machines.
Here's the before and after!

=== "Before"
    ```python hl_lines="1"
    # Completed in 15.2 seconds

    from typing import List
    from pathlib import Path

    import httpx
    from prefect import flow, task

    URL_FORMAT = (
        "https://www.cpc.ncep.noaa.gov/products/NMME/archive/"
        "{year:04d}{month:02d}0800/current/images/nino34.rescaling.ENSMEAN.png"
    )

    @task
    def download_image(year: int, month: int, directory: Path) -> Path:
        # download image from URL
        url = URL_FORMAT.format(year=year, month=month)
        resp = httpx.get(url)

        # save content to directory/YYYYMM.png
        file_path = (directory / url.split("/")[-1]).with_stem(f"{year:04d}{month:02d}")
        file_path.write_bytes(resp.content)
        return file_path

    @flow
    def download_nino_34_plumes_from_year(year: int) -> List[Path]:
        # create a directory to hold images
        directory = Path("data")
        directory.mkdir(exist_ok=True)

        # download all images
        file_paths = []
        for month in range(1, 12 + 1):
            file_path = download_image(year, month, directory)
            file_paths.append(file_path)
        return file_paths

    if __name__ == "__main__":
        download_nino_34_plumes_from_year(2022)
    ```

=== "After"

    ```python hl_lines="1 8 26 35"
    # Completed in 5.7 seconds

    from typing import List
    from pathlib import Path

    import httpx
    from prefect import flow, task
    from prefect_dask import DaskTaskRunner

    URL_FORMAT = (
        "https://www.cpc.ncep.noaa.gov/products/NMME/archive/"
        "{year:04d}{month:02d}0800/current/images/nino34.rescaling.ENSMEAN.png"
    )

    @task
    def download_image(year: int, month: int, directory: Path) -> Path:
        # download image from URL
        url = URL_FORMAT.format(year=year, month=month)
        resp = httpx.get(url)

        # save content to directory/YYYYMM.png
        file_path = (directory / url.split("/")[-1]).with_stem(f"{year:04d}{month:02d}")
        file_path.write_bytes(resp.content)
        return file_path

    @flow(task_runner=DaskTaskRunner(cluster_kwargs={"processes": False}))
    def download_nino_34_plumes_from_year(year: int) -> List[Path]:
        # create a directory to hold images
        directory = Path("data")
        directory.mkdir(exist_ok=True)

        # download all images
        file_paths = []
        for month in range(1, 12 + 1):
            file_path = download_image.submit(year, month, directory)
            file_paths.append(file_path)
        return file_paths

    if __name__ == "__main__":
        download_nino_34_plumes_from_year(2022)
    ```

The original flow completes in 15.2 seconds.

However, with just a few minor tweaks, we were able to reduce the runtime by nearly **three** folds, down to just **5.7** seconds!

### Integrate with Dask client/cluster and collections

Suppose you have an existing Dask client/cluster and collection, like a `dask.dataframe.DataFrame`, and you want to add observability.

With `prefect-dask`, there's no major overhaul necessary because Prefect was designed with incremental adoption in mind! It's as easy as:

1. Adding the imports
2. Sprinkling a few `task` and `flow` decorators
3. Using `get_dask_client` context manager on collections to distribute work across workers
4. Specifying the task runner and client's address in the flow decorator
5. Submitting the tasks to the flow's task runner

=== "Before"

    ```python
    import dask.dataframe
    import dask.distributed



    client = dask.distributed.Client()


    def read_data(start: str, end: str) -> dask.dataframe.DataFrame:
        df = dask.datasets.timeseries(start, end, partition_freq="4w")
        return df


    def process_data(df: dask.dataframe.DataFrame) -> dask.dataframe.DataFrame:

        df_yearly_avg = df.groupby(df.index.year).mean()
        return df_yearly_avg.compute()


    def dask_pipeline():
        df = read_data("1988", "2022")
        df_yearly_average = process_data(df)
        return df_yearly_average

    dask_pipeline()
    ```


=== "After"

    ```python hl_lines="3 4 8 13 15 19 21 22"
    import dask.dataframe
    import dask.distributed
    from prefect import flow, task
    from prefect_dask import DaskTaskRunner, get_dask_client

    client = dask.distributed.Client()

    @task
    def read_data(start: str, end: str) -> dask.dataframe.DataFrame:
        df = dask.datasets.timeseries(start, end, partition_freq="4w")
        return df

    @task
    def process_data(df: dask.dataframe.DataFrame) -> dask.dataframe.DataFrame:
        with get_dask_client():
            df_yearly_avg = df.groupby(df.index.year).mean()
            return df_yearly_avg.compute()

    @flow(task_runner=DaskTaskRunner(address=client.scheduler.address))
    def dask_pipeline():
        df = read_data.submit("1988", "2022")
        df_yearly_average = process_data.submit(df)
        return df_yearly_average

    dask_pipeline()
    ```

Now, you can conveniently see when each task completed, both in the terminal and the UI!

```bash
14:10:09.845 | INFO    | prefect.engine - Created flow run 'chocolate-pony' for flow 'dask-flow'
14:10:09.847 | INFO    | prefect.task_runner.dask - Connecting to an existing Dask cluster at tcp://127.0.0.1:59255
14:10:09.857 | INFO    | distributed.scheduler - Receive client connection: Client-8c1e0f24-9133-11ed-800e-86f2469c4e7a
14:10:09.859 | INFO    | distributed.core - Starting established connection to tcp://127.0.0.1:59516
14:10:09.862 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
14:10:11.344 | INFO    | Flow run 'chocolate-pony' - Created task run 'read_data-5bc97744-0' for task 'read_data'
14:10:11.626 | INFO    | Flow run 'chocolate-pony' - Submitted task run 'read_data-5bc97744-0' for execution.
14:10:11.795 | INFO    | Flow run 'chocolate-pony' - Created task run 'process_data-090555ba-0' for task 'process_data'
14:10:11.798 | INFO    | Flow run 'chocolate-pony' - Submitted task run 'process_data-090555ba-0' for execution.
14:10:13.279 | INFO    | Task run 'read_data-5bc97744-0' - Finished in state Completed()
14:11:43.539 | INFO    | Task run 'process_data-090555ba-0' - Finished in state Completed()
14:11:43.883 | INFO    | Flow run 'chocolate-pony' - Finished in state Completed('All states completed.')
```

## Resources

For additional examples, check out the [Usage Guide](usage_guide)!

### Installation

Get started by installing `prefect-dask`!

=== "pip"

    ```bash
    pip install -U prefect-dask
    ```

=== "conda"

    ```bash
    conda install -c conda-forge prefect-dask
    ```

Requires an installation of Python 3.7+.

We recommend using a Python virtual environment manager such as pipenv, conda, or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Feedback

If you encounter any bugs while using `prefect-dask`, feel free to open an issue in the [prefect](https://github.com/PrefectHQ/prefect) repository.

If you have any questions or issues while using `prefect-dask`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

### Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-dask`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Here are the steps:

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
7. `git commit`, `git push`, and create a pull request
