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
        - log_output (bool): whether or not to log notebook cell output to the
            papermill logger.
        - output_format (str, optional): Notebook output format, should be a valid
            nbconvert Exporter name. 'json' is treated as 'notebook'.
            Valid exporter names: asciidoc, custom, html, latex, markdown,
            notebook, pdf, python, rst, script, slides, webpdf. (default: notebook)
        - exporter_kwargs (dict, optional): The arguments used for initializing
            the exporter.
        - kernel_name (string, optional): kernel name to run the notebook with.
            If not provided, the default kernel will be used.
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        path: str = None,
        parameters: dict = None,
        log_output: bool = False,
        output_format: str = "notebook",
        exporter_kwargs: dict = None,
        kernel_name: str = None,
        **kwargs
    ):
        self.path = path
        self.parameters = parameters
        self.log_output = log_output
        self.output_format = output_format
        self.kernel_name = kernel_name
        self.exporter_kwargs = exporter_kwargs
        super().__init__(**kwargs)

    @defaults_from_attrs("path", "parameters", "output_format", "exporter_kwargs")
    def run(
        self,
        path: str = None,
        parameters: dict = None,
        output_format: str = None,
        exporter_kwargs: dict = None,
    ) -> str:
        """
        Run a Jupyter notebook and output as HTML, notebook, or other formats.

        Args:
        - path (string, optional): path to fetch the notebook from; can also be
            a cloud storage path
        - parameters (dict, optional): dictionary of parameters to use for the notebook
        - output_format (str, optional): Notebook output format, should be a valid
            nbconvert Exporter name. 'json' is treated as 'notebook'.
            Valid exporter names: asciidoc, custom, html, latex, markdown,
            notebook, pdf, python, rst, script, slides, webpdf. (default: notebook)
        - exporter_kwargs (dict, optional): The arguments used for initializing
            the exporter.
        """
        nb: nbformat.NotebookNode = pm.execute_notebook(
            path,
            "-",
            parameters=parameters,
            kernel_name=self.kernel_name,
            log_output=self.log_output,
        )
        if output_format == "json":
            output_format = "notebook"

        if exporter_kwargs is None:
            exporter_kwargs = {}

        exporter = nbconvert.get_exporter(output_format)
        body, resources = nbconvert.export(exporter, nb, **exporter_kwargs)
        return body
