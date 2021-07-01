---
sidebarDepth: 2
editLink: false
---
# String Templating Tasks
---
 ## StringFormatter
 <div class='class-sig' id='prefect-tasks-templates-strings-stringformatter'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.templates.strings.StringFormatter</p>(template=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/templates/strings.py#L7">[source]</a></span></div>

This task contains a template which is formatted with the results of any upstream tasks and returned.

Variables from `prefect.context` are also available for formatting.

**Args**:     <ul class="args"><li class="args">`template (str, optional)`: the optional _default_ template string to format at runtime;         can also be provided as a keyword to `run`, which takes precedence over this default.     </li><li class="args">`**kwargs (optional)`: additional keyword arguments to pass to the         standard Task constructor</li></ul> **Example**:


```python
from prefect import Flow
from prefect.tasks.templates import StringFormatter


message = '''
Hi {name}!  Welcome to Prefect.  Today is {today}.
'''

msg_task = StringFormatter(name="message body", template=message)

with Flow("string-template") as flow:
    output = msg_task(name="Marvin")

flow_state = flow.run()
print(flow_state.result[output].result)
# Hi Marvin!  Welcome to Prefect.  Today is 2019-08-28.

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-templates-strings-stringformatter-run'><p class="prefect-class">prefect.tasks.templates.strings.StringFormatter.run</p>(template=None, **format_kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/templates/strings.py#L46">[source]</a></span></div>
<p class="methods">Formats the template with the provided kwargs.<br><br>**Args**:     <ul class="args"><li class="args">`template (str, optional)`: the template string to format; if not         provided, `self.template` will be used     </li><li class="args">`**format_kwargs (optional)`: keyword arguments to use for formatting</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the formatted string</li></ul></p>|

---
<br>

 ## JinjaTemplate
 <div class='class-sig' id='prefect-tasks-templates-jinja2-jinjatemplate'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.templates.jinja2.JinjaTemplate</p>(template=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/templates/jinja2.py#L16">[source]</a></span></div>

This task contains a Jinja template which is formatted with the results of any upstream tasks and returned.

Variables from `prefect.context` will also be used for rendering.

**Args**:     <ul class="args"><li class="args">`template (str, optional)`: the optional _default_ template string to render at runtime;         can also be provided as a keyword to `run`, which takes precedence over this default.     </li><li class="args">`**kwargs (optional)`: additional keyword arguments to pass to the         standard Task constructor</li></ul> **Example**:


```python
from prefect import Flow
from prefect.tasks.templates import JinjaTemplate


message = '''
Hi {{name}}!  Welcome to Prefect.  Today is {{today}}.
'''

msg_task = JinjaTemplate(name="message body", template=message)

with Flow("string-template") as flow:
        output = msg_task(name="Marvin")

flow_state = flow.run()

print(flow_state.result[output].result)
# Hi Marvin!  Welcome to Prefect.  Today is 2019-08-28.

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-templates-jinja2-jinjatemplate-run'><p class="prefect-class">prefect.tasks.templates.jinja2.JinjaTemplate.run</p>(template=None, **format_kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/templates/jinja2.py#L56">[source]</a></span></div>
<p class="methods">Formats the Jinja Template with the provided kwargs.<br><br>**Args**:     <ul class="args"><li class="args">`template (str, optional)`: the template string to render; if not         provided, `self.template` will be used     </li><li class="args">`**format_kwargs (optional)`: keyword arguments to use for         rendering; note that variables from `prefect.context` will also be used</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the rendered string</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>