---
sidebarDepth: 0
---

## Flow Operators

Often times data pipelines are to large to develop as one `Flow`.  Flow operators allow developers to work on flows independently and then join them using flow operators.

:::warning Unintended Consequences
1. Target locations can change.
2. Parameter tasks can get overwritten when they are not unique. 
:::

### Disjoint Union
Flow disjoint allows users to create one flow from two flows.  Where the flows have no shared tasks or edges.  Flows that share names or slugs are renamed by appending the name of the flow.  

![underlying flow graph](docs/assets/operator_viz/disjoint_union.svg){.viz-xs .viz-padded}


The code for the diagram above

```python
from prefect import Flow, task, Parameter

@task
def add_one(a_number: int): 
    return a_number + 1

@task(log_stdout=True)
def print_result(the_result:int): 
    print(the_result)

with Flow("Add") as add_fl:
    a_number = Parameter("a_number", default=1)
    
    the_result = add_one(a_number)
    
    print_result(the_result)

@task
def sub_one(a_number: int):
    return a_number - 1


with Flow("Subtract") as subtract_fl:
    
    a_number = Parameter("a_number", default=1)
    
    the_result = sub_one(a_number)
    
    print_result(the_result)
    
```


This method is useful when a flow is dependent on another flow to run using 


