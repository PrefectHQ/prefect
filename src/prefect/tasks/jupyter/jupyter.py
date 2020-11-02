import nbconvert
import nbformat
import papermill as pm

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class JupyterTask(Task):
    """
    Task for running Jupyter Notebooks.
    In order to parametrize the notebook, you need to mark the parameters cell as described
        in the papermill documentation: https://papermill.readthedocs.io/en/latest/usage-parameterize.html

    Args:
        - notebook_path (string, optional): path to fetch the notebook from.
            Can be a cloud storage path.
            Can also be provided post-initialization by calling this task instance
        - notebook_params (dict, optional): dictionary of parameters to use for the notebook
            Can also be provided at runtime
        - as_html (bool, optional): whether to output as HTML. (default: True)
        - kernel_name (string, optional): kernel name to run the notebook with.
            If not provided, the default kernel will be used.
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        notebook_path: str = None,
        notebook_params: dict = None,
        as_html: bool = True,
        kernel_name: str = None,
        **kwargs
    ):
        self.notebook_path = notebook_path
        self.notebook_params = notebook_params
        self.as_html = as_html
        self.kernel_name = kernel_name
        super().__init__(**kwargs)

    @defaults_from_attrs("notebook_path", "notebook_params", "as_html")
    def run(
        self,
        notebook_path: str = None,
        notebook_params: dict = None,
        as_html: bool = None,
    ) -> str:
        """
        Run a Jupyter notebook and output as HTML or JSON

        Args:
        - notebook_path (string, optional): path to fetch the notebook from; can also be
            a cloud storage path
        - notebook_params (dict, optional): dictionary of parameters to use for the notebook
        - as_html (bool, optional): whether to output as HTML
        """
        nb: nbformat.NotebookNode = pm.execute_notebook(
            notebook_path, "-", parameters=notebook_params, kernel_name=self.kernel_name
        )
        if as_html:
            html_exporter = nbconvert.HTMLExporter()
            (body, resources) = html_exporter.from_notebook_node(nb)
            return body

        # return JSON format
        return nbformat.writes(nb)
