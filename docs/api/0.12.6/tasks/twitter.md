---
sidebarDepth: 2
editLink: false
---
# Twitter Tasks
---
Tasks for interacting with Twitter.
 ## LoadTweetReplies
 <div class='class-sig' id='prefect-tasks-twitter-twitter-loadtweetreplies'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.twitter.twitter.LoadTweetReplies</p>(user=None, tweet_id=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/twitter/twitter.py#L9">[source]</a></span></div>

A task for loading replies to a specific user's tweet. This task works by querying the 100 most recent replies to that user, then filtering for those that match the specified tweet id.

This code is based on the work of Matt Dickenson @mcdickenson https://mattdickenson.com/2019/03/02/extract-replies-to-tweet/

Note that _all_ initialization settings can be provided / overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`user (str)`: a Twitter user     </li><li class="args">`tweet_id (str)`: a tweet ID; replies to this tweet will be retrieved     </li><li class="args">`**kwargs (optional)`: additional kwargs to pass to the `Task` constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-twitter-twitter-loadtweetreplies-run'><p class="prefect-class">prefect.tasks.twitter.twitter.LoadTweetReplies.run</p>(user=None, tweet_id=None, credentials=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/twitter/twitter.py#L31">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`user (str)`: a Twitter user     </li><li class="args">`tweet_id (str)`: a tweet ID; replies to this tweet will be retrieved     </li><li class="args">`credentials(dict)`: a JSON document with four keys:         "api_key", "api_secret", "access_token", and "access_token_secret".</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>