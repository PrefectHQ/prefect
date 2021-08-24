---
sidebarDepth: 2
editLink: false
---
# Trello Tasks
---
Tasks for interacting with Trello
Note, to authenticate with the Trello API use upstream PrefectSecret tasks to pass in
'"TRELLO_API_KEY"' (see https://trello.com/app-key while logged in)
and '"TRELLO_SERVER_TOKEN"' (click the 'Token' link on https://trello.com/app-key to generate)
 ## CreateCard
 <div class='class-sig' id='prefect-tasks-trello-trello-createcard'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.trello.trello.CreateCard</p>(list_id=None, card_name=None, card_info=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/trello/trello.py#L7">[source]</a></span></div>

Task for creating a card on Trello, given the list to add it to.

**Args**:   <ul class="args"><li class="args">`list_id (str)`: the id of the list to add the new item.   </li><li class="args">`card_name (str, optional)`: the title of the card to add   </li><li class="args">`card_info (str, optional)`: the description for the back of the card   </li><li class="args">`**kwargs (dict, optional)`: additional arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-trello-trello-createcard-run'><p class="prefect-class">prefect.tasks.trello.trello.CreateCard.run</p>(list_id=None, card_name=None, card_info=None, trello_api_key=&quot;TRELLO_API_KEY&quot;, trello_server_token=&quot;TRELLO_SERVER_TOKEN&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/trello/trello.py#L31">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:   <ul class="args"><li class="args">`list_id (str)`: the id of the list to add the new item.   </li><li class="args">`card_name (str, optional)`: the title of the card to add   </li><li class="args">`card_info (str, optional)`: the description for the back of the card   </li><li class="args">`trello_api_key (str)`: the name of the Prefect Secret where you've stored your API key   </li><li class="args">`trello_server_token (str)`: the name of the Prefect Secret   where you've stored your server token</li></ul> **Returns**:   <ul class="args"><li class="args">Status code of POST request (200 for success)</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>