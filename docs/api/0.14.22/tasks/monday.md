---
sidebarDepth: 2
editLink: false
---
# Monday Tasks
---
Tasks for interacting with monday.com

Note, to authenticate with the Monday API add a Prefect Secret
called '"MONDAY_API_TOKEN"' that stores your Monday API Token.
 ## CreateItem
 <div class='class-sig' id='prefect-tasks-monday-monday-createitem'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.monday.monday.CreateItem</p>(board_id=None, group_id=None, item_name=None, column_values=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monday/monday.py#L9">[source]</a></span></div>

Task for creating items in a Monday board

**Args**:     <ul class="args"><li class="args">`board_id (int)`: the id of the board to add the new item     </li><li class="args">`group_id (str)`: the id of the group to add the new item     </li><li class="args">`item_name (str)`: the name of the item to be created     </li><li class="args">`column_values (dict, optional)`: any additional custom columns added to your board     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-monday-monday-createitem-run'><p class="prefect-class">prefect.tasks.monday.monday.CreateItem.run</p>(board_id=None, group_id=None, item_name=None, column_values=None, monday_api_token=&quot;MONDAY_API_TOKEN&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monday/monday.py#L37">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`board_id (int)`: the id of the board to add the new item     </li><li class="args">`group_id (str)`: the id of the group to add the new item     </li><li class="args">`item_name (str)`: the name of the item to be created     </li><li class="args">`column_values (dict, optional)`: any additional custom columns added to your board     </li><li class="args">`monday_api_token (str)`: the name of the Prefect Secret which stored your Monday         API Token.</li></ul> **Returns**:     <ul class="args"><li class="args">`int`: the id of the item created</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>