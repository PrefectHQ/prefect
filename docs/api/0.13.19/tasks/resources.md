---
sidebarDepth: 2
editLink: false
---
# ResourceManager Tasks
---
 ## ResourceManager
 <div class='class-sig' id='prefect-tasks-core-resource-manager-resourcemanager'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.resource_manager.ResourceManager</p>(resource_class, name=None, init_task_kwargs=None, setup_task_kwargs=None, cleanup_task_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/resource_manager.py#L121">[source]</a></span></div>

An object for managing temporary resources.

Used as a context manager, `ResourceManager` objects create tasks to setup and cleanup temporary objects used within a block of tasks.  Examples might include temporary Dask/Spark clusters, Docker containers, etc...

`ResourceManager` objects are usually created using the `resource_manager` decorator, but can be created directly using this class if desired.

For more information, see the docs for `resource_manager`.

**Args**:     <ul class="args"><li class="args">`resource_class (Callable)`: A callable (usually the class itself) for         creating an object that follows the `ResourceManager` protocol.     </li><li class="args">`name (str, optional)`: The resource name - defaults to the name of the         decorated class.     </li><li class="args">`init_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `init` task.     </li><li class="args">`setup_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `setup` task.     </li><li class="args">`cleanup_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `cleanup` task.</li></ul> **Example**:

Here's an example resource manager for creating a temporary local dask cluster as part of the flow.


```python
from prefect import resource_manager
from dask.distributed import Client

@resource_manager
class DaskCluster:
    def __init__(self, n_workers):
        self.n_workers = n_workers

    def setup(self):
        "Create a local dask cluster"
        return Client(n_workers=self.n_workers)

    def cleanup(self, client):
        "Cleanup the local dask cluster"
        client.close()

```

To use the `DaskCluster` resource manager as part of your Flow, you can use `DaskCluster` as a context manager:


```python
with Flow("example") as flow:
    n_workers = Parameter("n_workers")

    with DaskCluster(n_workers=n_workers) as client:
        some_task(client)
        some_other_task(client)

```


---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-resource-manager-resource-manager'><p class="prefect-class">prefect.tasks.core.resource_manager.resource_manager</p>(resource_class=None, name=None, init_task_kwargs=None, setup_task_kwargs=None, cleanup_task_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/resource_manager.py#L249">[source]</a></span></div>
<p class="methods">A decorator for creating a `ResourceManager` object.<br><br>Used as a context manager, `ResourceManager` objects create tasks to setup and cleanup temporary objects used within a block of tasks.  Examples might include temporary Dask/Spark clusters, Docker containers, etc...<br><br>Through usage a ResourceManager object adds three tasks to the graph:     - A `init` task, which returns an object that meets the `ResourceManager`       protocol. This protocol requires two methods:         * `setup(self) -> resource`: A method for creating the resource.             The return value from this will available to user tasks.         * `cleanup(self, resource) -> None`: A method for cleaning up the             resource.  This takes the return value from `setup` and             shouldn't return anything.     - A `setup` task, which calls the `setup` method on the `ResourceManager`     - A `cleanup` task, which calls the `cleanup` method on the `ResourceManager`.<br><br>**Args**:     <ul class="args"><li class="args">`resource_class (Callable)`: The decorated class.     </li><li class="args">`name (str, optional)`: The resource name - defaults to the name of the         decorated class.     </li><li class="args">`init_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `init` task.     </li><li class="args">`setup_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `setup` task.     </li><li class="args">`cleanup_task_kwargs (dict, optional)`: keyword arguments that will be         passed to the `Task` constructor for the `cleanup` task.</li></ul> **Returns**:     <ul class="args"><li class="args">`ResourceManager`: the created `ResourceManager` object.</li></ul> **Example**:<br><br>Here's an example resource manager for creating a temporary local dask cluster as part of the flow.<br><br><br><pre class="language-python"><code class="language-python"><span class="token keyword">from</span> prefect <span class="token keyword">import</span> resource_manager<br><span class="token keyword">from</span> dask.distributed <span class="token keyword">import</span> Client<br><br><span class="token decorator">@resource_manager</span><br><span class="token keyword">class</span> <span class="token class-name">DaskCluster</span><span class="token punctuation">:</span><br>    <span class="token keyword">def</span> <span class="token function">__init__</span><span class="token punctuation">(</span><span class="token builtin">self</span><span class="token punctuation">,</span> n_workers<span class="token punctuation">)</span><span class="token punctuation">:</span><br>        <span class="token builtin">self</span><span class="token operator">.</span>n_workers <span class="token operator">=</span> n_workers<br><br>    <span class="token keyword">def</span> <span class="token function">setup</span><span class="token punctuation">(</span><span class="token builtin">self</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>        <span class="token string">"</span><span class="token string">Create a local dask cluster</span><span class="token string">"</span><br>        <span class="token keyword">return</span> Client<span class="token punctuation">(</span>n_workers<span class="token operator">=</span><span class="token builtin">self</span><span class="token operator">.</span>n_workers<span class="token punctuation">)</span><br><br>    <span class="token keyword">def</span> <span class="token function">cleanup</span><span class="token punctuation">(</span><span class="token builtin">self</span><span class="token punctuation">,</span> client<span class="token punctuation">)</span><span class="token punctuation">:</span><br>        <span class="token string">"</span><span class="token string">Cleanup the local dask cluster</span><span class="token string">"</span><br>        client<span class="token operator">.</span>close<span class="token punctuation">(</span><span class="token punctuation">)</span><br></code></pre><br><br><br>To use the `DaskCluster` resource manager as part of your Flow, you can use `DaskCluster` as a context manager:<br><br><br><pre class="language-python"><code class="language-python"><span class="token keyword">with</span> Flow<span class="token punctuation">(</span><span class="token string">"</span><span class="token string">example</span><span class="token string">"</span><span class="token punctuation">)</span> <span class="token keyword">as</span> flow<span class="token punctuation">:</span><br>    n_workers <span class="token operator">=</span> Parameter<span class="token punctuation">(</span><span class="token string">"</span><span class="token string">n_workers</span><span class="token string">"</span><span class="token punctuation">)</span><br><br>    <span class="token keyword">with</span> DaskCluster<span class="token punctuation">(</span>n_workers<span class="token operator">=</span>n_workers<span class="token punctuation">)</span> <span class="token keyword">as</span> client<span class="token punctuation">:</span><br>        some_task<span class="token punctuation">(</span>client<span class="token punctuation">)</span><br>        some_other_task<span class="token punctuation">(</span>client<span class="token punctuation">)</span><br></code></pre><br><br><br>The `Task` returned by entering the `DaskCluster` context (i.e. the `client` part of  `as client`) is the output of the `setup` method on the `ResourceManager` class. A `Task` is automatically added to call the `cleanup` method (closing the Dask cluster) after all tasks under the context have completed. By default this `cleanup` task is configured with a trigger to always run if the `setup` task succeeds, and won't be set as a reference task.</p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>