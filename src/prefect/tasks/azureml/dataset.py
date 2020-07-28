from typing import Dict, List, Union, Optional

import azureml.core.dataset
from azureml.core.datastore import Datastore
from azureml.data import DataType, TabularDataset
from azureml.data.dataset_type_definitions import PromoteHeadersBehavior

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class DatasetCreateFromDelimitedFiles(Task):
    """
    Task for creating a TabularDataset from delimited files for use in a Azure Machine Learning
    service Workspace. The files should exist in a Datastore.  Note that all initialization
    arguments can optionally be provided or overwritten at runtime.

    Args:
        - dataset_name (str, optional): The name of the Dataset in the Workspace
        - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds the
            files.
        - path (Union[str, List[str]], optional): The path to the delimited files in the
            Datastore.
        - dataset_description (str, optional): Description of the Dataset.
        - dataset_tags (str, optional): Tags to associate with the Dataset.
        - include_path (bool, optional): Boolean to keep path information as column in the
            dataset.
        - infer_column_types (bool, optional): Boolean to infer column data types.
        - set_column_types (Dict[str, azureml.data.DataType], optional): A dictionary to set
            column data type, where key is column name and value is a `azureml.data.DataType`.
        - fine_grain_timestamp (str, optional): The name of column as fine grain timestamp.
        - coarse_grain_timestamp (str, optional): The name of column coarse grain timestamp.
        - separator (str, optional): The separator used to split columns.
        - header (azureml.data.dataset_type_definitions.PromoteHeadersBehavior, optional):
            Controls how column headers are promoted when reading from files. Defaults to
            assume that all files have the same header.
        - partition_format (str, optional): Specify the partition format of path. Defaults to
            None. The partition information of each path will be extracted into columns based
            on the specified format. Format part `{column_name}` creates string column, and
            `{column_name:yyyy/MM/dd/HH/mm/ss}` creates datetime column, where `yyyy`, `MM`,
            `dd`, `HH`, `mm` and `ss` are used to extrat year, month, day, hour, minute and
            second for the datetime type. The format should start from the position of first
            partition key until the end of file path. For example, given the path
            `../Germany/2019/01/01/data.csv` where the partition is by country and time,
            `partition_format="/{Country}/{PartitionDate:yyyy/MM/dd}/data.csv"` creates string
            column `Country` with value `Germany` and datetime column `PartitionDate` with
            value `2019-01-01`.
        - create_new_version (bool, optional): Boolean to register the dataset as a new version
            under the specified name.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        include_path: bool = False,
        infer_column_types: bool = True,
        set_column_types: Optional[Dict[str, DataType]] = None,
        fine_grain_timestamp: str = None,
        coarse_grain_timestamp: str = None,
        separator: str = ",",
        header: PromoteHeadersBehavior = PromoteHeadersBehavior.ALL_FILES_HAVE_SAME_HEADERS,
        partition_format: str = None,
        create_new_version: bool = False,
        **kwargs
    ) -> None:
        self.dataset_name = dataset_name
        self.datastore = datastore
        self.path = path
        self.dataset_description = dataset_description
        self.dataset_tags = dataset_tags or dict()
        self.include_path = include_path
        self.infer_column_types = infer_column_types
        self.set_column_types = set_column_types
        self.fine_grain_timestamp = fine_grain_timestamp
        self.coarse_grain_timestamp = coarse_grain_timestamp
        self.separator = separator
        self.header = header
        self.partition_format = partition_format
        self.create_new_version = create_new_version

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dataset_name",
        "datastore",
        "path",
        "dataset_description",
        "dataset_tags",
        "include_path",
        "infer_column_types",
        "set_column_types",
        "fine_grain_timestamp",
        "coarse_grain_timestamp",
        "separator",
        "header",
        "partition_format",
        "create_new_version",
    )
    def run(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        include_path: bool = False,
        infer_column_types: bool = True,
        set_column_types: Optional[Dict[str, DataType]] = None,
        fine_grain_timestamp: str = None,
        coarse_grain_timestamp: str = None,
        separator: str = ",",
        header: PromoteHeadersBehavior = PromoteHeadersBehavior.ALL_FILES_HAVE_SAME_HEADERS,
        partition_format: str = None,
        create_new_version: bool = False,
    ) -> TabularDataset:
        """
        Task run method.

        Args:
            - dataset_name (str, optional): The name of the Dataset in the Workspace
            - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds
                the files.
            - path (Union[str, List[str]], optional): The path to the delimited files in the
                Datastore.
            - dataset_description (str, optional): Description of the Dataset.
            - dataset_tags (str, optional): Tags to associate with the Dataset.
            - include_path (bool, optional): Boolean to keep path information as column in the
                dataset.
            - infer_column_types (bool, optional): Boolean to infer column data types.
            - set_column_types (Dict[str, azureml.data.DataType], optional): A dictionary to
                set column data type, where key is column name and value is a
                `azureml.data.DataType`.
            - fine_grain_timestamp (str, optional): The name of column as fine grain timestamp.
            - coarse_grain_timestamp (str, optional): The name of column coarse grain timestamp.
            - separator (str, optional): The separator used to split columns.
            - header (azureml.data.dataset_type_definitions.PromoteHeadersBehavior, optional):
                Controls how column headers are promoted when reading from files. Defaults to
                assume that all files have the same header.
            - partition_format (str, optional): Specify the partition format of path.
            - create_new_version (bool, optional): Boolean to register the dataset as a new
                version under the specified name.

        Returns:
            - azureml.data.TabularDataset: the created TabularDataset

        """
        if dataset_name is None:
            raise ValueError("A dataset_name must be provided.")

        if path is None:
            raise ValueError("A path must be provided.")

        if datastore is None:
            raise ValueError("A path must be provided.")

        if not isinstance(path, list):
            path = [path]

        dataset_tags = dataset_tags or dict()

        dataset = azureml.core.dataset.Dataset.Tabular.from_delimited_files(
            path=[(datastore, path_item) for path_item in path],
            include_path=include_path,
            infer_column_types=infer_column_types,
            set_column_types=set_column_types,
            separator=separator,
            header=header,
            partition_format=partition_format,
        )

        dataset = dataset.with_timestamp_columns(
            fine_grain_timestamp=fine_grain_timestamp,
            coarse_grain_timestamp=coarse_grain_timestamp,
            validate=True,
        )

        dataset = dataset.register(
            workspace=datastore.workspace,
            name=dataset_name,
            description=dataset_description,
            tags=dataset_tags,
            create_new_version=create_new_version,
        )

        return dataset


class DatasetCreateFromParquetFiles(Task):
    """
    Task for creating a TabularDataset from Parquet files for use in a Azure Machine Learning
    service Workspace. The files should exist in a Datastore.  Note that all initialization
    arguments can optionally be provided or overwritten at runtime.

    Args:
        - dataset_name (str, optional): The name of the Dataset in the Workspace
        - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds the
            files.
        - path (Union[str, List[str]], optional): The path to the delimited files in the Datastore.
        - dataset_description (str, optional): Description of the Dataset.
        - dataset_tags (str, optional): Tags to associate with the Dataset.
        - include_path (bool, optional): Boolean to keep path information as column in the dataset.
        - set_column_types (Dict[str, azureml.data.DataType], optional): A dictionary to set
            column data type, where key is column name and value is a `azureml.data.DataType`.
        - fine_grain_timestamp (str, optional): The name of column as fine grain timestamp.
        - coarse_grain_timestamp (str, optional): The name of column coarse grain timestamp.
        - partition_format (str, optional): Specify the partition format of path. Defaults to
            None. The partition information of each path will be extracted into columns based
            on the specified format. Format part `{column_name}` creates string column, and
            `{column_name:yyyy/MM/dd/HH/mm/ss}` creates datetime column, where `yyyy`, `MM`,
            `dd`, `HH`, `mm` and `ss` are used to extrat year, month, day, hour, minute and
            second for the datetime type. The format should start from the position of first
            partition key until the end of file path. For example, given the path
            `../Germany/2019/01/01/data.csv` where the partition is by country and time,
            `partition_format="/{Country}/{PartitionDate:yyyy/MM/dd}/data.csv"` creates string
            column `Country` with value `Germany` and datetime column `PartitionDate` with
            value `2019-01-01`.
        - create_new_version (bool, optional): Boolean to register the dataset as a new version
            under the specified name.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        include_path: bool = False,
        set_column_types: Optional[Dict[str, DataType]] = None,
        fine_grain_timestamp: str = None,
        coarse_grain_timestamp: str = None,
        partition_format: str = None,
        create_new_version: bool = False,
        **kwargs
    ) -> None:
        self.dataset_name = dataset_name
        self.datastore = datastore
        self.path = path
        self.dataset_description = dataset_description
        self.dataset_tags = dataset_tags or dict()
        self.include_path = include_path
        self.set_column_types = set_column_types
        self.fine_grain_timestamp = fine_grain_timestamp
        self.coarse_grain_timestamp = coarse_grain_timestamp
        self.partition_format = partition_format
        self.create_new_version = create_new_version

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dataset_name",
        "datastore",
        "path",
        "dataset_description",
        "dataset_tags",
        "include_path",
        "set_column_types",
        "fine_grain_timestamp",
        "coarse_grain_timestamp",
        "partition_format",
        "create_new_version",
    )
    def run(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        include_path: bool = False,
        set_column_types: Optional[Dict[str, DataType]] = None,
        fine_grain_timestamp: str = None,
        coarse_grain_timestamp: str = None,
        partition_format: str = None,
        create_new_version: bool = None,
    ) -> TabularDataset:
        """
        Task run method.

        Args:
            - dataset_name (str, optional): The name of the Dataset in the Workspace
            - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds
                the files.
            - path (Union[str, List[str]], optional): The path to the delimited files in the
                Datastore.
            - dataset_description (str, optional): Description of the Dataset.
            - dataset_tags (str, optional): Tags to associate with the Dataset.
            - include_path (bool, optional): Boolean to keep path information as column in the
                dataset.
            - set_column_types (Dict[str, azureml.data.DataType], optional): A dictionary to
                set column data type, where key is column name and value is a
                `azureml.data.DataType`.
            - fine_grain_timestamp (str, optional): The name of column as fine grain timestamp.
            - coarse_grain_timestamp (str, optional): The name of column coarse grain timestamp.
            - partition_format (str, optional): Specify the partition format of path.
            - create_new_version (bool, optional): Boolean to register the dataset as a new
                version under the specified name.

        Returns:
            - azureml.data.TabularDataset: the created TabularDataset.
        """
        if dataset_name is None:
            raise ValueError("A dataset_name must be provided.")

        if path is None:
            raise ValueError("A path must be provided.")

        if datastore is None:
            raise ValueError("A path must be provided.")

        if not isinstance(path, list):
            path = [path]

        dataset_tags = dataset_tags or dict()

        dataset = azureml.core.dataset.Dataset.Tabular.from_parquet_files(
            path=[(datastore, path_item) for path_item in path],
            include_path=include_path,
            set_column_types=set_column_types,
            partition_format=partition_format,
        )

        dataset = dataset.with_timestamp_columns(
            fine_grain_timestamp=fine_grain_timestamp,
            coarse_grain_timestamp=coarse_grain_timestamp,
            validate=True,
        )

        dataset = dataset.register(
            workspace=datastore.workspace,
            name=dataset_name,
            description=dataset_description,
            tags=dataset_tags,
            create_new_version=create_new_version,
        )

        return dataset


class DatasetCreateFromFiles(Task):
    """
    Task for creating a FileDataset from files for use in a Azure Machine Learning service
    Workspace. The files should exist in a Datastore.  Note that all initialization arguments
    can optionally be provided or overwritten at runtime.

    Args:
        - dataset_name (str, optional): The name of the Dataset in the Workspace
        - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds the
            files.
        - path (Union[str, List[str]], optional): The path to the delimited files in the Datastore.
        - dataset_description (str, optional): Description of the Dataset.
        - dataset_tags (str, optional): Tags to associate with the Dataset.
        - create_new_version (bool, optional): Boolean to register the dataset as a new version
            under the specified name.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        create_new_version: bool = False,
        **kwargs
    ) -> None:
        self.dataset_name = dataset_name
        self.datastore = datastore
        self.path = path
        self.dataset_description = dataset_description
        self.dataset_tags = dataset_tags or dict()
        self.create_new_version = create_new_version

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dataset_name",
        "datastore",
        "path",
        "dataset_description",
        "dataset_tags",
        "create_new_version",
    )
    def run(
        self,
        dataset_name: str = None,
        datastore: Datastore = None,
        path: Union[str, List[str]] = None,
        dataset_description: str = "",
        dataset_tags: Optional[Dict[str, str]] = None,
        create_new_version: bool = False,
    ) -> azureml.data.FileDataset:
        """
        Task run method.

        Args:
            - dataset_name (str, optional): The name of the Dataset in the Workspace
            - datastore (azureml.core.datastore.Datastore, optional): The Datastore which holds
                the files.
            - path (Union[str, List[str]], optional): The path to the delimited files in the
                Datastore.
            - dataset_description (str, optional): Description of the Dataset.
            - dataset_tags (str, optional): Tags to associate with the Dataset.
            - create_new_version (bool, optional): Boolean to register the dataset as a new
                version under the specified name.

        Returns:
            - azureml.data.FileDataset: the created FileDataset
        """
        if dataset_name is None:
            raise ValueError("A dataset_name must be provided.")

        if path is None:
            raise ValueError("A path must be provided.")

        if datastore is None:
            raise ValueError("A path must be provided.")

        if not isinstance(path, list):
            path = [path]

        dataset_tags = dataset_tags or dict()

        dataset = azureml.core.dataset.Dataset.File.from_files(
            path=[(datastore, path_item) for path_item in path]
        )

        dataset = dataset.register(
            workspace=datastore.workspace,
            name=dataset_name,
            description=dataset_description,
            tags=dataset_tags,
            create_new_version=create_new_version,
        )

        return dataset
