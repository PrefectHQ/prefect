---
sidebarDepth: 1
---

# State
---
 ## State

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.state.State(data=None, message=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L12)</span>
Create a new State object.
data (Any, optional): Defaults to None. A data payload for the state.
message (str or Exception, optional): Defaults to None. A message about the
state, which could be an Exception (or Signal) that caused it.

 ####  ```prefect.engine.state.State.is_failed()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L64)</span>


 ####  ```prefect.engine.state.State.is_finished()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L58)</span>


 ####  ```prefect.engine.state.State.is_pending()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L52)</span>


 ####  ```prefect.engine.state.State.is_running()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L55)</span>


 ####  ```prefect.engine.state.State.is_successful()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/state.py#L61)</span>



