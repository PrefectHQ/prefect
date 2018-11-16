# Advanced Features <Badge text="advanced" type="warn"/><Badge text="0.3.2+"/>
> Topics covered: _mapping tasks_, _resource throttling_, _parallelization_, _parameters_, _flow.run() keyword arguments_

::: tip Practice Makes Prefect
A notebook containing all code presented in this tutorial can be downloaded [here](/notebooks/advanced-mapping.ipynb).
:::

Here we will dig into some of the more advanced features that Prefect offers; in the process, we will construct a real world workflow that highlights how Prefect can be a powerful tool for local development, allowing us to expressively and efficiently create, inspect and extend custom data workflows.

::: tip Our Goal
Inspired by the revival of the TV show "The X-Files" along with recent advances in Natural Language Processing, we seek to scrape transcripts of every X-Files episode from the internet and save them to a database so that we can create a chatbot based on the character of Dana Scully (actually creating the chatbot is left as an exercise to the reader).

All code examples are intended to be executable on your local machine within an interactive Python or IPython session. 
:::

## Outline
We will proceed in stages, introducing Prefect functionality as we go:
1. First, we will scrape a specific episode to test our scraping logic; this will only require the core Prefect building blocks.
2. Next, we will compile a _list_ of all episodes, and then scrape each individual episode; for this we will introduce the concept of "mapping" a Task to efficiently re-use our scraping logic across each episode.
3. To speed up processing time, we will re-execute our flow to exploit the inherit _parallelism_ of our mapped tasks; moreover, to prevent opening too many simultaneous connections to the website, we will _throttle_ the scraping tasks.  To achieve this we need to use a new Prefect _executor_.  We will also save the results of this run to prevent re-running the scraping jobs as we extend our flow further.
4. Finally, we want to create a simple sqlite database and store all of our data in it.

As we proceed, we hope to ensure that our Flow is _reproducible_ and _reusable_ in the future.

::: warning BeautifulSoup4
To easily navigate the webpages, we will be using the package [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), which is not a requirement for Prefect.  To install `BeautifulSoup4`, run either:
```
pip install beautifulsoup4 # OR
conda install beautifulsoup4
```
:::

## Setting up the flow for a single episode

Luckily for us, [Inside the X-Files](http://www.insidethex.co.uk/) has maintained a curated list of X-Files episode transcripts for the past 20 years; moreover, the webpage is still written using basic 1990s HTML, meaning it's very easy to scrape!

Using this as our source of transcripts, let's scrape a single episode of "The X-Files", starting with ["Jose Chung's From Outer Space"](http://www.insidethex.co.uk/transcrp/scrp320.htm) (which features a guest appearance by Alex Trebek).

We begin by setting up two Prefect tasks:
- `retrieve_url`: a task which simply pulls the raw HTML to our local machine
- `scrape_dialogue`: a task which takes that HTML, and processes it to extract the relevant dialogue by character

To ease in, let's import everything we need and create the `retrieve_url` task:

```python
import requests
from bs4 import BeautifulSoup
from prefect import task, Flow, Parameter


@task(tags=["web"])
def retrieve_url(url):
    """
    Given a URL (string), retrieves html and
    returns the html as a string.
    """

    html = requests.get(url)
    if html.ok:
        return html.text
    else:
        raise ValueError("{} could not be retrieved.".format(url))
```
Foreseeing our need to throttle the tasks which open web connections, we have _tagged_ the `retrieve_url` task with `"web"` (any string can be provided as a tag).

Next we create our `scrape_dialogue` task, which will contain the logic for parsing the raw HTML and extracting only the episode name and the dialogue (represented as a list of tuples `[(character, text)]`).  Because this task does not need to access the web, we do not need to tag it:

```python
@task
def scrape_dialogue(episode_html):
    """
    Given a string of html representing an episode page,
    returns a tuple of (title, [(character, text)]) of the dialogue from that
    episode
    """

    episode = BeautifulSoup(episode_html, 'html.parser')
    
    title = episode.title.text.rstrip(' *').replace("'", "''")
    convos = episode.find_all('b') or episode.find_all('span', {'class': 'char'})
    dialogue = []
    for item in convos:
        who = item.text.rstrip(': ').rstrip(' *').replace("'", "''")
        what = str(item.next_sibling).rstrip(' *').replace("'", "''")
        dialogue.append((who, what))
    return (title, dialogue)
```

Now that we have our tasks, all that's left is to put them together into a flow; because we want to re-use these tasks for other episodes, we will leave the URL as a `Parameter` which should be provided at runtime. We assume you have familiarized yourself with [the basics](etl.html) of constructing a Prefect flow and the [use of `Parameters`](calculator.html).

```python
with Flow("xfiles") as flow:
    url = Parameter("url")
    episode = retrieve_url(url)
    dialogue = scrape_dialogue(episode)


flow.visualize()
```

![](/simple_flow.svg) {style="text-align: center;"}


Awesome!  We've constructed our flow and everything looks good; all that's left is to run it.  When we call `flow.run()` we need to provide two keywords:
- `parameters`: a dictionary of the required parameter values (in our case, `url`)
- `return_tasks`: a list of the tasks we want returned in the flow's state; in this case we ask for the `dialogue` task so we can see if our scraping worked as intended

We then print the first five spoken lines of the episode.

```python
episode_url = "http://www.insidethex.co.uk/transcrp/scrp320.htm"
outer_space = flow.run(parameters={"url": episode_url},
                       return_tasks=[dialogue])

state = outer_space.result[dialogue] # the `State` object for the dialogue task
first_five_spoken_lines = state.result[1][:5] # state.result is a tuple (episode_name, [dialogue])
print(''.join([f'{speaker}: {words}' for speaker, words in first_five_spoken_lines))
```

    ROKY CRIKENSON:  Yeah, this is Roky. I checked all the connections. I
    don''t know why all the power''s down out here. I''m going to have to come
    in and get some more equipment. Yeah, yeah... yeah, I''ll need several of
    those. All right...
    
    HAROLD LAMB:  Um... I don''t want to scare you, but... I think I''m madly
    in love with you.
    
    CHRISSY GIORGIO:  Harold, I like you a lot too, but this is our first
    date. I mean, I think that we need more time to get to know one another.
    
    HAROLD LAMB:  Oh my God... oh my God...
    
    CHRISSY GIORGIO:  Harold, what are those things?
    

Intrigued? Great! We can spot check against [the actual website](http://www.insidethex.co.uk/transcrp/scrp320.htm), and it looks like our scraping logic is sound.  Let's scale up and scrape _everything_.

## Scaling to all episodes

Now that we're reasonably confident in our scraping logic, we want to reproduce the above example for _every_ episode while maintaining backwards compatibility for a single page.  To do so, we need to compile a list of the URLs for every episode, and then proceed to scrape each one.

We achieve this with a single new task:
- `create_episode_list`: given the main page's raw html, creates a list consisting of the absolute URLs of all episode transcripts and returns that list.  If the `bypass` flag is set to `True`, the `base_url` is simply returned in a single element list.  This gives the ability to scrape a single episode in the future using this flow.


```python
@task
def create_episode_list(base_url, main_html, bypass):
    """
    Given the main page html, creates a list of episode URLs
    """

    if bypass:
        return [base_url]
    
    main_page = BeautifulSoup(main_html, 'html.parser')
    
    episodes = []
    for link in main_page.find_all('a'):
        url = link.get('href')
        if 'transcrp/scrp' in (url or ''):
            episodes.append(base_url + url)

    return episodes
```

Now that we have all of the building blocks for scraping everything, the question remains: how do we fit it all together?  Without Prefect, you might consider writing a loop that iterates over the results of `create_episode_list`.  For each episode, you could put everything within a `try / except` block to capture any errors and let other episodes proceed.  If you then wanted to exploit parallelism, you'd need to refactor further, taking into account that you _don't yet know_ how many episodes `create_episode_list` will return.  

Any of these ideas would work, but consider this: we've already written the code that we _want_ executed; everything else is additional boilerplate to avoid the various errors and negative outcomes that might arise.  This is _precisely_ where Prefect can be so useful - if we piece our functions together into a flow, everything is taken care of and the intent of our code is still immediately apparent, without having to wade through the defensive logic.

In our current situation, instead of a loop, we utilize the `map()` method of tasks.  At a high level, at runtime `task.map(iterable_task)` is roughly equivalent to:
```python
results = iterable_task.run()

for item in results:
    task.run(item)
```
Prefect will _dynamically_ create a task for each element of results, without needing to know how many there will be _a priori_.

We now proceed to actually construct the flow; you'll notice a few additional lines from the first flow we created:
- a `bypass` parameter for allowing us to bypass scraping the homepage for a list of all episodes
- in this case, we will use the `retrieve_url` task for the home page as well as all the episode pages (being able to re-use our functions with new arguments is one of the great benefits of a functional workflow tool)
- `retrieve_url` and `scrape_dialogue` will now be called with `.map()` as discussed above

```python
with Flow("xfiles") as flow:
    url = Parameter("url")
    bypass = Parameter("bypass", default=False, required=False)
    home_page = retrieve_url(url)
    episodes = create_episode_list(url, home_page, bypass=bypass)
    episode = retrieve_url.map(episodes)
    dialogue = scrape_dialogue.map(episode)
```

::: tip Parameters
The `Parameter` class has a few useful settings that we need in the above example:
- `default`: The default value the parameter should take; in our case, we want `bypass=False`
- `required`: a boolean specifying whether or not the parameter is required at flow runtime; if not provided, the default value will be used
:::

<a name="scrape_single_box"></a>
:::tip Scraping a single episode
To reproduce [the first example](#setting-up-the-flow-for-a-single-episode) we ran using our new flow, we could now run:
```python
episode_url = "http://www.insidethex.co.uk/transcrp/scrp320.htm"
outer_space = flow.run(parameters={"url": episode_url, "bypass": True},
                       start_tasks=[bypass, episodes, url],
                       return_tasks=[dialogue])
```
In this case, we provide `bypass=True` so that the full episode list is not scraped; morever, we explicitly tell the flow to begin execution with the Parameters and the `create_episode_list` task, avoiding the task which would retrieve the homepage html.  See the diagram above to better understand what is occuring here - we'll see this pattern again shortly.
:::

To highlight the benefits of `map`, note that we went from scraping a single episode to scraping all episodes by writing one new function and recompliling our flow with minimal change: our original flow had _three_ tasks, while our new flow has _hundreds_!

```python
flow.visualize()
```

![](/full_scrape_flow.svg) {style="text-align: center;"}

::: tip How mapped tasks are returned
In a normal flow run, `flow_state.result[task]` returns the post-run `State` of the `task` (e.g., `Success("Task run succeeded")`).  If, however, the task was the result of calling `.map()`, `flow_state.result[task]` will be a _list_ of states - one for each mapped instance.
:::

Now let's run our flow, time its execution, and print the states for the first five scraped episodes:
```python
%%time
scraped_state = flow.run(parameters={"url": "http://www.insidethex.co.uk/"}, return_tasks=[dialogue])
#    CPU times: user 7.48 s, sys: 241 ms, total: 7.73 s
#    Wall time: 4min 46s

dialogue_state = scraped_state.result[dialogue] # list of State objects
print('\n'.join([f'{s.result[0]}: {s}' for s in dialogue_state[:5]]))
```

    BABYLON - 1AYW04: Success("Task run succeeded.")
    Pilot - 1X79: Success("Task run succeeded.")
    Deep Throat - 1X01: Success("Task run succeeded.")
    Squeeze - 1X02: Success("Task run succeeded.")
    Conduit - 1X03: Success("Task run succeeded.")


Great - 5 minutes isn't so bad!  An astute reader might notice that each mapped task is ["embarassingly parallel"](https://en.wikipedia.org/wiki/Embarrassingly_parallel). When running locally, Prefect will default to synchronous execution (with the `Synchronous` executor), so this property was not taken advantage of during execution.

In order to allow for parallel execution of tasks, we don't need to "recompile" our flow: we simply provide an executor which can handle parallelism in our call to `run`.  In the local case, Prefect offers the `DaskExecutor` for executing parallel flows.  These execution pipelines can either spawn new processes (`processes=True`), or only use threads; we have chosen to use `processes=True` in our example below.

:::tip What is an executor, anyway?
A Prefect executor is the core driver of computation - an executor specifies _how_ and _where_ each task in a flow should be run.
:::

This is great, but what if, under the hood, we end up with 20 requests going to this website simultaneously?  As good citizens of the internet, we should actively avoid this situation - to do so, we use the `throttle` keyword along with the fact that we proactively "tagged" our scraping tasks as `"web"` (for more information on throttling, see the [Task Throttling Tutorial](throttling.md)).

::: warning System limits
Using parallelism locally can open large numbers of ["file descriptors"](https://stackoverflow.com/a/5256705/1617887) on your machine and occasionally cause cryptic errors - you should check your system limit and increase it if necessary.

If you are following along and executing the code locally, it is recommended you do so using an interactive Python or IPython session; because the `DaskExecutor` will spawn new subprocesses, [issues can arise if executed within a script incorrectly](https://docs.python.org/3/library/multiprocessing.html#the-spawn-and-forkserver-start-methods).
:::

```python
from prefect.engine.executors import DaskExecutor

executor = DaskExecutor(processes=True)

%%time
scraped_state = flow.run(parameters={"url": "http://www.insidethex.co.uk/"},
               return_tasks=flow.tasks,
               executor=executor,
               throttle={"web": 3})

#    CPU times: user 9.7 s, sys: 1.67 s, total: 11.4 s
#    Wall time: 1min 34s

dialogue_state = scraped_state.result[dialogue] # list of State objects
print('\n'.join([f'{s.result[0]}: {s}' for s in dialogue_state[:5]]))
```

    BABYLON - 1AYW04: Success("Task run succeeded.")
    Pilot - 1X79: Success("Task run succeeded.")
    Deep Throat - 1X01: Success("Task run succeeded.")
    Squeeze - 1X02: Success("Task run succeeded.")
    Conduit - 1X03: Success("Task run succeeded.")


Awesome - we significantly improved our execution speed practically for free!

## Extend flow to write to a database

Now that we have successfully scraped all of the dialogue, the next natural step is to store this in a database for querying.  In order to ensure our entire workflow remains reproducible in the future, we want to extend the current flow with new tasks (as opposed to creating a new flow from scratch).  To this end, we first create two new tasks:
- `create_db`: creates a new `"XFILES"` table if one does not already exist
- `insert_episode`: inserts dialogue into the `"XFILES"` table

As before, we tag each task with `"db"` so that we can throttle database connections when we actually run the flow (strictly speaking, this isn't necessary for a `sqlite3` database, we will still include it for the sake of illustration).


```python
import sqlite3
from contextlib import closing


@task(tags=["db"])
def create_db(db_file):
    with closing(sqlite3.connect(db_file)) as conn:
        with closing(conn.cursor()) as c:
            create_cmd = '''CREATE TABLE IF NOT EXISTS XFILES (EPISODE TEXT, CHARACTER TEXT, TEXT TEXT)'''
            c.execute(create_cmd)
            conn.commit()

    
@task(tags=["db"])
def insert_episode(db_file, episode):
    with closing(sqlite3.connect(db_file)) as conn:
        with closing(conn.cursor()) as c:
            title, dialogue = episode
            insert_cmd = "INSERT INTO XFILES (EPISODE, CHARACTER, TEXT) VALUES\n"
            values = ',\n'.join(["('{0}', '{1}', '{2}')".format(title, *row) for row in dialogue]) + ";"
            c.execute(insert_cmd + values)
            conn.commit()
```

To extend our flow, we can simply use our current `flow` to open a context manager and add tasks like normal.  Note that we are utilizing the fact that `dialogue` is a task that was defined in our current session.

```python
from prefect import unmapped

with flow:
    db_file = Parameter("db_file")
    db = create_db(db_file)
    final = insert_episode.map(episode=dialogue, db_file=unmapped(db_file), 
                               upstream_tasks=[unmapped(db)])
```

::: tip task.map()
In the above example, we utilize a new call signature for `task.map()`.  It is often the case that some arguments to your task should _not_ be mapped over (they remain static).  This can be specified with the special `unmapped` container which we use to wrap such arguments to `map`.  In our example above, the argument `"db_file"` is _not_ mapped over and is simply provided as-is to `insert_episode`.  

You also might notice the special `upstream_tasks` keyword argument; this is not unique to `map` and is simply a way of functionally specifying upstream dependencies which do not pass any data.
:::


```python
flow.visualize()
```

![](/full_db_flow.svg) {style="text-align: center;"}

We are now ready to execute our flow! Of course, we have _already_ scraped all the dialogue - there's no real need to redo all that work.  This is where our previous flow state (`scraped_state`) comes in handy! Recall that `scraped_state.result` will be a dictionary of tasks to their corresponding states; consequently we can feed this information to the next flow run via the `task_states` keyword argument.  These states will then be used in determining whether each task should be run or whether they are already finished.  Because we have added _new_ tasks to the flow, the new tasks will not have a corresponding state in this dictionary and will run as expected.  

Moreover, to avoid a lot of unnecsesary processing, we can explicitly tell the flow to start running at the three tasks we just added using the `start_tasks` keyword argument:


```python
state = flow.run(parameters={"url": "http://www.insidethex.co.uk/", 
                             "db_file": "xfiles_db.sqlite"}, 
                 executor=executor,
                 throttle={"web": 3, "db": 10},
                 task_states=scraped_state.result,
                 start_tasks=[final, db, db_file])
```

And now, with our DB set up and populated, we can start to tackle the _real_ questions, such as: how many times was "programming" mentioned in all of The X-Files?


```python
with closing(sqlite3.connect("xfiles_db.sqlite")) as conn:
        with closing(conn.cursor()) as c:
            create_cmd = '''SELECT * FROM XFILES WHERE TEXT LIKE '%programming%';'''
            c.execute(create_cmd)
            programming_mentions = c.fetchall()

print(programming_mentions)
```

    [('First Person Shooter - 7X13',
      'BYERS',
      'Langly did some programming for them.  He created all of the\nbad guys.'),
     ('The Springfield Files - X3601',
      'HOMER',
      'Now son, they do a lot of quality programming too. Haa haa haa! I kill me.'),
     ('Kill Switch - 5X11',
      'BYERS',
      'This CD has some kind of enhanced background data. Lots of code. Maybe a programming design.')]

Disappointing, especially considering "The Springfield Files" was a Simpson's episode spoof of The X-Files.

## Reusability

Suppose some time has passed, and a _new_ transcript has been uploaded - we've already put together all the necessary logic for going from a URL to the database, but how can we reuse that logic?  Simple - we use the [same pattern we used for scraping a single episode above](#scrape_single_box)!

Fun fact: The X-Files resulted in a spinoff TV series called "The Lone Gunmen"; the transcripts of this series are also [posted on the website we've been using](http://www.insidethex.co.uk/scripts.htm#tlg), so let's scrape Episode 5 using our already constructed flow; to do so, we'll utilize our custom `bypass` flag along with the `start_tasks` keyword argument for avoiding the initial scrape of the home page:


```python
final = flow.run(parameters={"url": "http://www.insidethex.co.uk/transcrp/tlg105.htm",
                             "bypass": True,
                             "db_file": "xfiles_db.sqlite"},
                 start_tasks=[bypass, db_file, episodes, url])


with closing(sqlite3.connect("xfiles_db.sqlite")) as conn:
        with closing(conn.cursor()) as c:
            create_cmd = '''SELECT * FROM XFILES WHERE TEXT LIKE '%programming%';'''
            c.execute(create_cmd)
            programming_mentions = c.fetchall()

print(programming_mentions)
```

    [('First Person Shooter - 7X13',
      'BYERS',
      'Langly did some programming for them.  He created all of the\nbad guys.'),
     ('The Springfield Files - X3601',
      'HOMER',
      'Now son, they do a lot of quality programming too. Haa haa haa! I kill me.'),
     ('Kill Switch - 5X11',
      'BYERS',
      'This CD has some kind of enhanced background data. Lots of code. Maybe a programming design.')]
     ('Planet of the Frohikes - 1AEB05',
      'FROHIKE',
      'It's a pretty neat bit of programming.')]

Yes it is, Frohike, yes it is.
