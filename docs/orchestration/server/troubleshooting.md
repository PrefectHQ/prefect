# Troubleshooting

Having trouble with Prefect Server? This page contains solutions to common problems.

## How to know if there's a problem

After running `prefect server start`, you should be able to view the Prefect UI in a web browser at the address [http://localhost:8080](http://localhost:8080). This can work even if the server hasn't fully started yet.

You'll know there's a problem if the color of the connection menu in the upper-right-corner Prefect UI transitions between yellow and red, and never turns green.

You'll see the message `Couldn't connect to Prefect Server at http://localhost:4200/graphql` when you click on the connection menu.

![](/orchestration/server/could-not-connect.png)

**Don't panic!** The troubleshooting steps in this section might help.

## The Hasura container failed to start

After you run `prefect server start`, the server's Docker containers should start. However, the Hasura container might fail to start if Docker doesn't have enough memory.

When this happens, the following message will appear in your terminal after you run `prefect server start`:

```
t-hasura-1 exited with code 137
```

!!! tip Finding this line
    You may need to search with your terminal to find this line of output &mdash; it won't be the last line printed.


The solution to this problem is configuring Docker to use more memory. The default in Docker Desktop is 2GB, which may not be enough to run Prefect Server. We recommend giving Docker at least 8GB of memory.

!!! tip Docker memory is shared
    Note that the memory that you configure for Docker is shared between all running containers.


You can adjust the memory that Docker makes available to containers in the Settings or Preferences menu of Docker Desktop. To find this menu, consult the User Manual for your version of Docker Desktop in the [Docker Desktop documentation](https://docs.docker.com/desktop/).


![](/orchestration/server/docker-memory-setting.png)

## Where to go next

The [Prefect Community Slack](https://prefect.io/slack) is a great place to ask for help! You can also write a new post in our [GitHub Discussion Board](https://github.com/PrefectHQ/prefect/discussions/new).

!!! tip Save the output from `prefect server start`
    If you ask for help, someone may ask to see the text that the `prefect server start` command generated when you ran it. Saving a copy of that text now will help speed up troubleshooting later!

