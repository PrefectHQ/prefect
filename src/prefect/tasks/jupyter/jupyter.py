import nbconvert
import nbformat
import papermill as pm

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class ExecuteNotebook(Task):
    """
    Task for running Jupyter Notebooks.
    In order to parametrize the notebook, you need to mark the parameters cell as described in
        the papermill documentation: https://papermill.readthedocs.io/en/latest/usage-parameterize.html

    Args:
        - path (string, optional): path to fetch the notebook from.
            Can be a cloud storage path.
            Can also be provided post-initialization by calling this task instance
        - parameters (dict, optional): dictionary of parameters to use for the notebook
            Can also be provided at runtime
        - output_format (str, optional): Notebook output format.
            Currently supported: json, html (default: json)
        - kernel_name (string, optional): kernel name to run the notebook with.
            If not provided, the default kernel will be used.
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        path: str = None,
        parameters: dict = None,
        output_format: str = "json",
        kernel_name: str = None,
        **kwargs
    ):
        self.path = path
        self.parameters = parameters
        self.output_format = output_format
        self.kernel_name = kernel_name
        super().__init__(**kwargs)

    @defaults_from_attrs("path", "parameters", "output_format")
    def run(
        self,
        path: str = None,
        parameters: dict = None,
        output_format: str = None,
    ) -> str:
        """
        Run a Jupyter notebook and output as HTML or JSON

        Args:
        - path (string, optional): path to fetch the notebook from; can also be
            a cloud storage path
        - parameters (dict, optional): dictionary of parameters to use for the notebook
        - output_format (str, optional): Notebook output format.
            Currently supported: json, html (default: json)
        """
        nb: nbformat.NotebookNode = pm.execute_notebook(
            path, "-", parameters=parameters, kernel_name=self.kernel_name
        )
        if output_format == "json":
            return nbformat.writes(nb)
        if output_format == "html":
            html_exporter = nbconvert.HTMLExporter()
            (body, resources) = html_exporter.from_notebook_node(nb)
            return body

        raise NotImplementedError("Notebook output %s not supported", output_format)
