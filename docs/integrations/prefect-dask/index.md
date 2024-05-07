# prefect-dask

The `prefect-dask` integration makes it easy to include distributed processing for your flows. Check out the examples below to get started!

## Get started

## Installation

Install `prefect-dask` into a virtual environment:

<div class="terminal">
```bash
pip install -U prefect-dask
```
</div>

## Integrate with Prefect flows

Say your flow downloads many images to train your machine learning model. Unfortunately, it takes a long time to download your flows because your code is running sequentially.

After installing `prefect-dask` you can parallelize your flow in three simple steps:

1. Add the import: `from prefect_dask import DaskTaskRunner`
2. Specify the task runner in the flow decorator: `@flow(task_runner=DaskTaskRunner)`
3. Submit tasks to the flow's task runner: `a_task.submit(*args, **kwargs)`

In the example below, the code that runs in parallel using Dask runs in about a third of the time as the sequential!
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

On tests by the Prefect team, the original flow completed in 15.2 seconds when run sequentially.
With just the switch to the DaskTaskRunner, the runtime was reduced to **5.7** seconds!

For additional time savings with Dask, you could distribute large workloads over multiple machines.

### Integrate with Dask client/cluster

Suppose you have an existing Dask client/cluster such as a `dask.dataframe.DataFrame`, and you want to add observability.

With `prefect-dask`, no major overhaul necessary because Prefect was designed with incremental adoption in mind. Here are the steps:

1. Add imports
2. Add `task` and `flow` decorators
3. Use `get_dask_client` context manager to distribute work across Dask workers
4. Specify the task runner and client's address in the flow decorator
5. Submit the tasks to the flow's task runner

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

    if __name__ == "__main__":
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

    if __name__ == "__main__":
        dask_pipeline()
    ```

Run the code and see when each task completes in the CLI or the UI.

## Resources

For additional examples, check out the [Usage Guide](usage_guide)!
