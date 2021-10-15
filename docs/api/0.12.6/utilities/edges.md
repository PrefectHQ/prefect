---
sidebarDepth: 2
editLink: false
---
# Edge Utilities
---
 ## unmapped
 <div class='class-sig' id='prefect-utilities-edges-unmapped'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.edges.unmapped</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/edges.py#L57">[source]</a></span></div>

A container for specifying that a task should _not_ be mapped over when called with `task.map`.

**Args**:     <ul class="args"><li class="args">`value (Any)`: the task or value to mark as "unmapped"; if not a Task         subclass, Prefect will attempt to convert it to one when the edge is         created.</li></ul>**Example**:     
```python
    from prefect import Flow, Task, unmapped

    class AddTask(Task):
        def run(self, x, y):
            return x + y

    class ListTask(Task):
        def run(self):
            return [1, 2, 3]

    with Flow("My Flow"):
        add = AddTask()
        ll = ListTask()
        result = add.map(x=ll, y=unmapped(5), upstream_tasks=[unmapped(Task())])

```


---
<br>

 ## mapped
 <div class='class-sig' id='prefect-utilities-edges-mapped'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.edges.mapped</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/edges.py#L25">[source]</a></span></div>

A container for specifying that a task should be mapped over when supplied as the input to another task.

**Args**:     <ul class="args"><li class="args">`value (Any)`: the task or value to mark as "mapped"; if not a Task         subclass, Prefect will attempt to convert it to one when the edge is         created.</li></ul>**Example**:     
```python
    from prefect import Flow, Task, mapped

    class AddTask(Task):
        def run(self, x, y):
            return x + y

    class ListTask(Task):
        def run(self):
            return [1, 2, 3]

    with Flow("My Flow"):
        add = AddTask()
        ll = ListTask()
        result = add(x=mapped(ll), y=5)

```


---
<br>

 ## flatten
 <div class='class-sig' id='prefect-utilities-edges-flatten'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.edges.flatten</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/edges.py#L89">[source]</a></span></div>

A container for specifying that a task's output should be flattened before being passed to another task.

**Args**:     <ul class="args"><li class="args">`value (Any)`: the task or value to mark as "flattened"; if not a Task         subclass, Prefect will attempt to convert it to one when the edge is         created.</li></ul>**Example**:     
```python
    from prefect import Flow, Task, flatten

    class Add(Task):
        def run(self, x):
            return x + 100

    class NestedListTask(Task):
        def run(self):
            return [[1], [2, 3]]

    with Flow("My Flow"):
        add = Add()
        ll = NestedListTask()

        result = add.map(x=flatten(ll))

    # result represents [101, 102, 103]

```


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>
