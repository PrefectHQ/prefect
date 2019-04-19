"""
This example demonstrates the use of the Prefect platform for machine learning.
Data is downloaded from a URL, extracted, and loaded into Numpy/Pandas.
Then a series of mathematical operations are performed on the columns, to create
a feature set from the raw data. Finally, the features are stitched together and
passed into a Principal Components Analysis for dimensionality reduction.

The Flow makes use of a number of Prefect features, including Parameters,
the set_dependencies method for Tasks that don't pass data, task mapping,
and custom Task classes.
"""

import os
import pathlib
import zipfile
from typing import Any, Dict, List
from urllib.request import urlretrieve

import numpy as np

import pandas as pd
from prefect import Flow, Parameter, Task, task, unmapped
from sklearn.decomposition import PCA


# tasks to fetch and prepare data
@task
def mkdir(dirname: str):
    """
    Make a directory on the local filesystem, starting from the active directory.
    """
    pathlib.Path(dirname).mkdir(exist_ok=True)


@task
def file_from_link(link: str) -> str:
    """
    Given a URL of a hosted file, retrieve just the name of the file.
    """
    rev_link = link[::-1]
    return rev_link[: rev_link.find("/")][::-1]


@task
def download_data(link: str, target_filename: str):
    """
    Submit an HTTP request to a URL to retrieve its content.

    Args:
        - link (str): the URL from which data will be requested
        - target_filename (str): the desired filename of the result
    """
    target_filepath = "data/" + target_filename
    if not os.path.exists(target_filepath):
        urlretrieve(link, target_filepath)


@task
def unzip_data(zip_filename: str):
    """
    Unzip a file and place its contents in the data/ directory.
    """
    zip_filepath = "data/" + zip_filename
    with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
        zip_ref.extractall("data")


@task
def get_rootdir(zip_filename: str):
    """
    Get the name of the root directory of the contents of a zip following extraction.
    """
    zip_filepath = "data/" + zip_filename
    with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
        rootdir = zip_ref.namelist()[0]
    return rootdir


@task
def read_csv(
    rootdir: str, table_name: str, nrows: int = None, exclude_cols: List[str] = None
):
    """
    Read the contents of a CSV into a Pandas DataFrame.

    This is built specifically for the file structure of the Lahman database.

    Args:
        - rootdir (str): name of the top-level directory where the data is stored
        - table_name (str): name of the data table to be retrieved
        - nrows (int, optional): defaults to all rows; otherwise, number of rows to load
        - exclude_cols (List[str], optional): columns to be excluded, by name

    Returns:
        - pd.DataFrame: the contents of the CSV
    """
    filepath = os.path.join("data", rootdir, "core", table_name + ".csv")
    df = pd.read_csv(filepath, nrows=None)
    return df.drop(exclude_cols, axis=1)


@task
def get_colnames(table: pd.DataFrame) -> List[str]:
    """
    Get column names from a DataFrame.
    """
    return list(table.columns)


@task
def get_cols(table: pd.DataFrame) -> List[np.ndarray]:
    """
    Get list of arrays corresponding to the columns of a DataFrame.
    """
    return list(table.values.T)


# data manipulation tasks
@task
def impute(data: np.ndarray, replacement_dict: Dict[Any, Any]) -> np.ndarray:
    """
    Replace any instances of a set of values with corresponding new values.

    The replacements are provided in a dictionary.
    The keys are the values to be replaced,
    and the values are the values to replace with.

    Args:
        - data (np.ndarray): data in which the replacements should be made
        - replacement_dict (Dict[Any, Any]): what to replace, and what to replace it with

    Returns:
        - np.ndarray: data with values replaced
    """
    for old, new in replacement_dict.items():
        if np.isnan(old):
            data[pd.isnull(data)] = new
        else:
            data[data == old] = new
    return data


@task
def cast(data: np.ndarray, new_type: type) -> np.ndarray:
    """
    Cast all the values of an array to a new data type.

    Args:
        - data (np.ndarray): data to be cast
        - new_type (type): type to be cast to

    Returns:
        - np.ndarray: the data in its new type
    """
    return data.astype(new_type)


@task
def get(values: List[np.ndarray], keys: List[str], key: str) -> np.ndarray:
    """
    Retrieve the value associated with a key given a list of keys and list of values.

    Essentially a utility to make use of dicts that have been broken into
    a list of keys and a list of values.

    Args:
        - values (List[np.ndarray]): values associated with keys
        - keys (List[str]): keys to choose from
        - key (str): the chosen key

    Returns:
        - np.ndarray: the value associated with the chosen key
    """
    return values[keys.index(key)]


@task
def concatenate(arrays: List[np.ndarray]) -> np.ndarray:
    """
    Concatenate multiple arrays along the last axis.
    for 1D arrays, make a 2D array of columns.
    """
    for i, a in enumerate(arrays):
        if len(a.shape) == 1:
            arrays[i] = np.expand_dims(a, -1)
    return np.concatenate(arrays, axis=-1)


@task
def dot(arrays: List[np.ndarray]) -> np.ndarray:
    """
    Calculate the dot product of two or more arrays.
    """
    return np.linalg.multi_dot(arrays)


# sabermetric calculation tasks
@task
def babip(
    h: np.ndarray, hr: np.ndarray, ab: np.ndarray, k: np.ndarray, sf: np.ndarray
) -> np.ndarray:
    """Calculate Batting Average on Balls In Play statistic."""
    X1 = h - hr
    X2 = ab - k - hr + sf
    impute_array = np.zeros_like(X1)
    return np.divide(
        X1.astype(np.float16), X2, out=impute_array.astype(np.float16), where=X2 != 0
    )


@task
def obp(
    h: np.ndarray, bb: np.ndarray, hbp: np.ndarray, ab: np.ndarray, sf: np.ndarray
) -> np.ndarray:
    """Calculate On-Base Percentage statistic."""
    X1 = h + bb + hbp
    X2 = ab + bb + hbp + sf
    impute_array = np.zeros_like(X1)
    return np.divide(
        X1.astype(np.float16), X2, out=impute_array.astype(np.float16), where=X2 != 0
    )


# utility
class DataFrame:
    """A utility class to provide convenient syntax for grabbing columns as a Task."""

    def __init__(self, cols: "Task", colnames: "Task"):
        self.cols = cols
        self.colnames = colnames

    def __getitem__(self, key: str):
        return get(self.cols, self.colnames, key)


# let's do some ML for fun
class PCATask(Task):
    def __init__(self, *args, task_kwargs={}, **kwargs):
        self.pca_model = PCA(*args, **kwargs)
        super().__init__(**task_kwargs)

    def fit(self, X):
        self.pca_model.fit(X)

    def transform(self, X):
        return self.pca_model.transform(X)

    def run(self, X):
        self.fit(X)
        return self.transform(X)


with Flow("Sabermetrics") as flow:
    link = Parameter("link")
    table = Parameter("table")

    # get data from the web
    zip_filename = file_from_link(link)
    mk_data = mkdir("data")

    dl_task = download_data(link, zip_filename, upstream_tasks=[mk_data])

    unzip = unzip_data(zip_filename, upstream_tasks=[dl_task])
    rootdir = get_rootdir(zip_filename, upstream_tasks=[unzip])

    exclude_cols = ["playerID", "yearID", "stint", "teamID", "lgID"]
    data = read_csv(rootdir, table, exclude_cols=exclude_cols)
    colnames = get_colnames(data)
    data_cols = get_cols(data)

    # clean data
    clean = impute.map(data_cols, replacement_dict=unmapped({np.nan: 0}))
    clean = cast.map(clean, new_type=unmapped(np.int))
    clean = DataFrame(clean, colnames)

    # stats
    singles = clean["H"] - clean["2B"] - clean["3B"] - clean["HR"]
    hit_types = concatenate([singles, clean["2B"], clean["3B"], clean["HR"]])
    total_bases = dot([hit_types, np.array([1, 2, 3, 4])])
    PA = clean["AB"] + clean["BB"] + clean["HBP"] + clean["SH"] + clean["SF"]
    BBp = clean["BB"] / PA
    Kp = clean["SO"] / PA
    OBP = obp(clean["H"], clean["BB"], clean["HBP"], clean["AB"], clean["SF"])
    SLG = total_bases / clean["AB"]
    AVG = clean["H"] / clean["AB"]
    ISO = SLG - AVG
    BABIP = babip(clean["H"], clean["HR"], clean["AB"], clean["SO"], clean["SF"])

    features = concatenate([PA, BBp, Kp, OBP, SLG, AVG, ISO, BABIP])
    # impute the failed divisions (div by 0)
    features = impute(features, {np.nan: 0.0})
    PCs = PCATask(n_components=2)(features)


url = "https://github.com/chadwickbureau/baseballdatabank/archive/v2019.2.zip"
table = "Batting"
state = flow.run(parameters={"link": url, "table": table})

print(state.result[features].result.shape)
print(state.result[PCs].result.shape)
# (105861, 8)
# (105861, 2)
