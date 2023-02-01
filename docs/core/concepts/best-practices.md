# Best Practices

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

## Writing Prefect code

To maximize the clarity of your Prefect code, we recommend organizing your scripts in a few sections:

1. Import any task classes you need
2. Define any custom task functions
3. Instantiate any task classes
4. Build your flow using the functional API if possible, and the imperative API where appropriate.

### Example

```python
#--------------------------------------------------------------
# Imports
#--------------------------------------------------------------

# basic imports
from prefect import Flow, Parameter, task

# specific task class imports
from prefect.tasks.shell import ShellTask


#--------------------------------------------------------------
# Define custom task functions
#--------------------------------------------------------------

@task
def plus_one(x):
    """A task that adds 1 to a number"""
    return x + 1

@task
def build_command(name):
    return 'echo "HELLO, {}!"'.format(name)

#--------------------------------------------------------------
# Instantiate task classes
#--------------------------------------------------------------

run_in_bash = ShellTask(name='run a command in bash')

#--------------------------------------------------------------
# Open a Flow context and use the functional API (if possible)
#--------------------------------------------------------------

with Flow('Best Practices') as flow:
    # store the result of each task call, even if you don't use the result again
    two = plus_one(1)

    # for clarity, call each task on its own line
    name = Parameter('name')
    cmd = build_command(name=name)
    shell_result = run_in_bash(command=cmd)

    # use the imperative API where appropriate
    shell_result.set_upstream(two)
```
