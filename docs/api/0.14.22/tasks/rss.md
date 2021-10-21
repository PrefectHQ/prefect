---
sidebarDepth: 2
editLink: false
---
# RSS Tasks
---
Tasks for interacting with RSS feeds.
 ## ParseRSSFeed
 <div class='class-sig' id='prefect-tasks-rss-feed-parserssfeed'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.rss.feed.ParseRSSFeed</p>(feed_url=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/rss/feed.py#L9">[source]</a></span></div>

Task for parsing RSS feeds. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`feed_url (str)`: A remote URL pointing to an RSS feed     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-rss-feed-parserssfeed-run'><p class="prefect-class">prefect.tasks.rss.feed.ParseRSSFeed.run</p>(feed_url=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/rss/feed.py#L25">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`feed_url (str)`: A remote URL pointing to an RSS feed</li></ul> Return:     - FeedParserDict: A dictionary representing the information from the         parsed feed. The object is accessable through indexing and attributes.<br><br>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `feed_url` is `None`</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>