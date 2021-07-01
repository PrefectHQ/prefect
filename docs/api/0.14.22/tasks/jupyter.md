---
sidebarDepth: 2
editLink: false
---
# Jupyter Tasks
---
A collection of tasks for running Jupyter notebooks.
 ## ExecuteNotebook
 <div class='class-sig' id='prefect-tasks-jupyter-jupyter-executenotebook'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.jupyter.jupyter.ExecuteNotebook</p>(path=None, parameters=None, log_output=False, output_format=&quot;notebook&quot;, exporter_kwargs=None, kernel_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jupyter/jupyter.py#L9">[source]</a></span></div>

Task for running Jupyter Notebooks. In order to parametrize the notebook, you need to mark the parameters cell as described in     the papermill documentation: https://papermill.readthedocs.io/en/latest/usage-parameterize.html

**Args**:     <ul class="args"><li class="args">`path (string, optional)`: path to fetch the notebook from.         Can be a cloud storage path.         Can also be provided post-initialization by calling this task instance     </li><li class="args">`parameters (dict, optional)`: dictionary of parameters to use for the notebook         Can also be provided at runtime     </li><li class="args">`log_output (bool)`: whether or not to log notebook cell output to the         papermill logger.     </li><li class="args">`output_format (str, optional)`: Notebook output format, should be a valid         nbconvert Exporter name. 'json' is treated as 'notebook'.         Valid exporter names: asciidoc, custom, html, latex, markdown,         notebook, pdf, python, rst, script, slides, webpdf. (default: notebook)     </li><li class="args">`exporter_kwargs (dict, optional)`: The arguments used for initializing         the exporter.     </li><li class="args">`kernel_name (string, optional)`: kernel name to run the notebook with.         If not provided, the default kernel will be used.     </li><li class="args">`**kwargs`: additional keyword arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-jupyter-jupyter-executenotebook-run'><p class="prefect-class">prefect.tasks.jupyter.jupyter.ExecuteNotebook.run</p>(path=None, parameters=None, output_format=None, exporter_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jupyter/jupyter.py#L52">[source]</a></span></div>
<p class="methods">Run a Jupyter notebook and output as HTML, notebook, or other formats.<br><br>**Args**: <ul class="args"><li class="args">`path (string, optional)`: path to fetch the notebook from; can also be     a cloud storage path </li><li class="args">`parameters (dict, optional)`: dictionary of parameters to use for the notebook </li><li class="args">`output_format (str, optional)`: Notebook output format, should be a valid     nbconvert Exporter name. 'json' is treated as 'notebook'.     Valid exporter names: asciidoc, custom, html, latex, markdown,     notebook, pdf, python, rst, script, slides, webpdf. (default: notebook) </li><li class="args">`exporter_kwargs (dict, optional)`: The arguments used for initializing     the exporter.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>