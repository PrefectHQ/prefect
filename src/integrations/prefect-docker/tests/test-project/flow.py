import sys

import numpy as np
import pandas as pd

from prefect import flow, get_run_logger, task


@task
def random_dataframe(N: int = 10):
    df = pd.DataFrame(np.random.randint(0, 100, size=(N, 3)), columns=list("ABC"))
    return df


@task
def log_summary(df: pd.DataFrame):
    logger = get_run_logger()
    logger.info(df.describe())


@flow
def pandas_flow(N: int = 10):
    df = random_dataframe(N)
    log_summary(df)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        N = sys.argv[1]
        pandas_flow(N)
    else:
        pandas_flow()
