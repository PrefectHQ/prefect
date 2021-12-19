from sodaspark import scan

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SodaSparkScan(Task):
    """
    Task for running a SodaSpark scan given a scan definition and a Spark Dataframe.
    For information about SodaSpark please refer to https://docs.soda.io/soda-spark/install-and-use.html.
    SodaSpark uses PySpark under the hood, hence you need Java to be installed on
    the machine where you run this task.

    Args:
        - scan_def (str, optional): scan definition.
          Can be either a path to a YAML file containing the scan definition.
          Please refer to https://docs.soda.io/soda-sql/scan-yaml.html for more information.
          or the scan definition given as a valid YAML string
        - df (pyspark.sql.DataFrame, optional): Spark DataFrame.
          DataFrame where to run tests defined in the scan definition.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, scan_def: str = None, df=None, **kwargs):
        self.scan_def = scan_def
        self.df = df
        super().__init__(**kwargs)

    @defaults_from_attrs("scan_def", "df")
    def run(self, scan_def: str = None, df=None):
        """
        Task run method. Execute a scan against a Spark DataFrame.

        Args:
            - scan_def (str, optional): scan definition.
              Can be either a path to a YAML file containing the scan definition.
              Please refer to https://docs.soda.io/soda-sql/scan-yaml.html for more information.
              or the scan definition given as a valid YAML string
            - df (pyspark.sql.DataFrame, optional): Spark DataFrame.
              DataFrame where to run tests defined in the scan definition.

        Returns:
            - A SodaSpark ScanResult
        Raises:
            - ValueError if scan_def is None or not a valid path to a YAML file
            - ValueError if df is None
        """
        if scan_def is None:
            raise ValueError("scan_def cannot be None")
        if df is None:
            raise ValueError("df cannot be None")

        result = scan.execute(scan_definition=scan_def, df=df)
        return result
