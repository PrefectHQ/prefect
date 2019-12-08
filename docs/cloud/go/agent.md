# Running a Local Agent with Supervisor

[[toc]]

## Starting Local Agent Through CLI

In a previous example you started your Local Agent in process right off of the Flow object itself. This is great for iteration and testing but for production use you will want to run your Agents in different long-standing processes so they can reliably run multiple Flows. If you Flow was deployed with Local Storage, as the _ETL_ Flow was on a previous page, then the Flow was stored in your root `/.prefect/flows/` directory. Unless otherwise specified the Local Agent will default to looking at this path for a Flow when a Flow Run is created. This means that you may start a Local Agent anywhere with and it will be able to run _any_ Flows that are available in the path that it is provided.

To start the Local Agent from the CLI run the `prefect agent start` command. Provide it with an Agent type, in this case `local`, and your RUNNER token that was created during the previous [Create a Runner Token](/cloud/go/configure.html#create-a-runner-token) step.

```bash
$ prefect agent start local --token $YOUR_RUNNER_TOKEN
```

You should see output similar to the logs shown from the previous in-process call to `run_agent()`. Hopefully now it starts to become evident that the RUNNER token is best persisted somewhere where it can easily be retrieved and provided to the starting of Agents so you are not required to paste it every time.

When you create a Flow Run then your Flow should be deployed by the Local Agent just as it was during the [Run Flow with Prefect Cloud](/cloud/go/first.html#run-flow-with-prefect-cloud) section. This means that you can now attempt registering multiple Flows with Prefect Cloud and this Local Agent will deploy them when you create their respective Flow Runs!

It is not always desireable to have to run a Local Agent in the foreground and be responsible for the life of that process. Luckily Prefect has built in mechanisms in conjunction with the use of [Supervisor](http://supervisord.org/introduction.html) to manage your Agent processes. Whether you are running a Local Agent on your local machine or standing it up on a server somewhere, Supervisor is going to be a battle tested and resilient tool in your aresnal!

## Starting Local Agent in the Background with Supervisor

Since you're already using Prefect then Supervisor can be quickly and easily installed with `pip install supervisor`. For more information on Supervisor installation visit their [documentation](http://supervisord.org/installing.html).

The Prefect CLI has an installation command for the Local Agent which will output a `supervisord.conf` file that you can save and run using Supervisor. To see the contents of what this file will look like run the following command:

```bash
$ prefect agent install local --token $YOUR_RUNNER_TOKEN
```

This will give you output that you can provide to Supervisor in order to run your Local Agent. To run this for the first time save this output to a file called `supervisord.conf` and run the following command to start your Local Agent from the `supervisord.conf` file:

```
$ supervisord
```

Your Local Agent is now up and running in the background with Supervisor! This is an extermely useful tool for managing Agent processes in a non-invasive way and should work on any Unix based machine. Below are some helpful commands when working with Supervisor and when you are ready it is time to move on to learning more about the other various [storage options]() the Local Agent can use for deploying your Flows.

### Useful Supervisor Commands

To open an interactive prompt for inspection:

```
$ supervisorctl
```

If you ever need to edit your `supervisord.conf` file and restart:

```
$ supervisorctl reload
```

To inspect the status of your Local Agent use the interactive supervisorctl command:

```
$ supervisorctl
fg prefect-agent
```

To stop all running programs:

```
$ supervisorctl stop all
```

For more information on configuring supervisor, please see [http://supervisord.org/configuration.html](http://supervisord.org/configuration.html). To configure supervisor logging, please see [http://supervisord.org/logging.html](http://supervisord.org/logging.html).
