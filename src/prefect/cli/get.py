import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args


@click.group(hidden=True)
def get():
    """
    Get commands that refer to querying Prefect API metadata.

    \b
    Usage:
        $ prefect get [OBJECT]

    \b
    Arguments:
        flow-runs   Query flow runs
        flows       Query flows
        projects    Query projects
        tasks       Query tasks
        logs        Query logs

    \b
    Examples:
        $ prefect get flows
        NAME      VERSION   PROJECT NAME   AGE
        My-Flow   3         My-Project     3 days ago

    \b
        $ prefect get flows --project New-Proj --all-versions
        NAME        VERSION   PROJECT NAME   AGE
        Test-Flow   2         New-Proj       22 hours ago
        Test-Flow   1         New-Proj       1 month ago

    \b
        $ prefect get tasks --flow-name Test-Flow
        NAME          FLOW NAME   FLOW VERSION   AGE          MAPPED   TYPE
        first_task    Test-Flow   1              5 days ago   False    \
prefect.tasks.core.function.FunctionTask
        second_task   Test-Flow   1              5 days ago   True     \
prefect.tasks.core.function.FunctionTask
    """


@get.command(hidden=True)
@click.option("--name", "-n", help="A flow name to query.", hidden=True)
@click.option("--version", "-v", type=int, help="A flow version to query.", hidden=True)
@click.option("--project", "-p", help="The name of a project to query.", hidden=True)
@click.option(
    "--limit", "-l", default=10, help="A limit amount of flows to query.", hidden=True
)
@click.option(
    "--all-versions", is_flag=True, help="Query all flow versions.", hidden=True
)
def flows(name, version, project, limit, all_versions):
    """
    Query information regarding your Prefect flows.

    \b
    Options:
        --name, -n      TEXT    A flow name to query
        --version, -v   TEXT    A flow version to query
        --project, -p   TEXT    The name of a project to query
        --limit, -l     INTEGER A limit amount of flows to query, defaults to 10
        --all-versions          Output all versions of a flow, default shows most recent
    """

    distinct_on = EnumValue("name")
    if all_versions:
        distinct_on = None

    where_clause = {
        "_and": {
            "name": {"_eq": name},
            "version": {"_eq": version},
            "project": {"name": {"_eq": project}},
        }
    }

    query_results = {
        "name": True,
        "version": True,
        "created": True,
        "id": True,
        "project": {"name": True},
    }

    headers = ["NAME", "VERSION", "AGE", "ID", "PROJECT NAME"]

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": where_clause,
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                    "distinct_on": distinct_on,
                    "limit": limit,
                },
            ): query_results
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow

    output = []
    for item in flow_data:
        result_output = [
            item.name,
            item.version,
            pendulum.parse(item.created).diff_for_humans(),
            item.id,
            item.project.name,
        ]

        output.append(result_output)

    click.echo(
        tabulate(
            output, headers=headers, tablefmt="plain", numalign="left", stralign="left"
        )
    )


@get.command(hidden=True)
@click.option("--name", "-n", help="A project name to query.", hidden=True)
def projects(name):
    """
    Query information regarding your Prefect projects.

    \b
    Options:
        --name, -n      TEXT    A project name to query
    """
    query = {
        "query": {
            with_args(
                "project",
                {
                    "where": {"_and": {"name": {"_eq": name}}},
                    "order_by": {"name": EnumValue("asc")},
                },
            ): {
                "name": True,
                "created": True,
                "description": True,
                with_args("flows_aggregate", {"distinct_on": EnumValue("name")}): {
                    EnumValue("aggregate"): EnumValue("count")
                },
            }
        }
    }

    result = Client().graphql(query)

    project_data = result.data.project

    output = []
    for item in project_data:
        output.append(
            [
                item.name,
                item.flows_aggregate.aggregate.count,
                pendulum.parse(item.created).diff_for_humans(),
                item.description,
            ]
        )

    click.echo(
        tabulate(
            output,
            headers=["NAME", "FLOW COUNT", "AGE", "DESCRIPTION"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@get.command(hidden=True)
@click.option(
    "--limit",
    "-l",
    default=10,
    help="A limit amount of flow runs to query.",
    hidden=True,
)
@click.option("--flow", "-f", help="Specify a flow's runs to query.", hidden=True)
@click.option("--project", "-p", help="Specify a project's runs to query.", hidden=True)
@click.option(
    "--started",
    "-s",
    is_flag=True,
    help="Only retrieve started flow runs.",
    hidden=True,
)
def flow_runs(limit, flow, project, started):
    """
    Query information regarding Prefect flow runs.

    \b
    Options:
        --limit, l          INTEGER A limit amount of flow runs to query, defaults to 10
        --flow, -f          TEXT    Name of a flow to query for runs
        --project, -p       TEXT    Name of a project to query
        --started, -s               Only retrieve started flow runs, default shows `Scheduled` runs
    """

    if started:
        order = {"start_time": EnumValue("desc")}

        where = {
            "_and": {
                "flow": {
                    "_and": {
                        "name": {"_eq": flow},
                        "project": {"name": {"_eq": project}},
                    }
                },
                "start_time": {"_is_null": False},
            }
        }
    else:
        order = {"created": EnumValue("desc")}

        where = {
            "flow": {
                "_and": {"name": {"_eq": flow}, "project": {"name": {"_eq": project}}}
            }
        }

    query = {
        "query": {
            with_args(
                "flow_run", {"where": where, "limit": limit, "order_by": order}
            ): {
                "flow": {"name": True},
                "id": True,
                "created": True,
                "state": True,
                "name": True,
                "start_time": True,
            }
        }
    }

    result = Client().graphql(query)

    flow_run_data = result.data.flow_run

    output = []
    for item in flow_run_data:
        start_time = (
            pendulum.parse(item.start_time).to_datetime_string()
            if item.start_time
            else None
        )
        output.append(
            [
                item.name,
                item.flow.name,
                item.state,
                pendulum.parse(item.created).diff_for_humans(),
                start_time,
                item.id,
            ]
        )

    click.echo(
        tabulate(
            output,
            headers=[
                "NAME",
                "FLOW NAME",
                "STATE",
                "AGE",
                "START TIME",
                "ID",
            ],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@get.command(hidden=True)
@click.option("--name", "-n", help="A task name to query", hidden=True)
@click.option("--flow-name", "-fn", help="A flow name to query", hidden=True)
@click.option(
    "--flow-version", "-fv", type=int, help="A flow version to query.", hidden=True
)
@click.option("--project", "-p", help="The name of a project to query.", hidden=True)
@click.option(
    "--limit", "-l", default=10, help="A limit amount of tasks to query.", hidden=True
)
def tasks(name, flow_name, flow_version, project, limit):
    """
    Query information regarding your Prefect tasks.

    \b
    Options:
        --name, -n          TEXT    A task name to query
        --flow-name, -fn    TEXT    A flow name to query
        --flow-version, -fv INTEGER A flow version to query
        --project, -p       TEXT    The name of a project to query
        --limit, -l         INTEGER A limit amount of tasks to query, defaults to 10
    """

    where_clause = {
        "_and": {
            "name": {"_eq": name},
            "flow": {
                "name": {"_eq": flow_name},
                "version": {"_eq": flow_version},
                "project": {"name": {"_eq": project}},
            },
        }
    }

    query = {
        "query": {
            with_args(
                "task",
                {
                    "where": where_clause,
                    "limit": limit,
                    "order_by": {"created": EnumValue("desc")},
                },
            ): {
                "name": True,
                "created": True,
                "flow": {"name": True, "version": True},
                "mapped": True,
                "type": True,
            }
        }
    }

    result = Client().graphql(query)

    task_data = result.data.task

    output = []
    for item in task_data:
        output.append(
            [
                item.name,
                item.flow.name,
                item.flow.version,
                pendulum.parse(item.created).diff_for_humans(),
                item.mapped,
                item.type,
            ]
        )

    click.echo(
        tabulate(
            output,
            headers=["NAME", "FLOW NAME", "FLOW VERSION", "AGE", "MAPPED", "TYPE"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@get.command(hidden=True)
@click.option(
    "--name", "-n", required=False, help="A flow run name to query", hidden=True
)
@click.option("--id", required=False, help="A flow run ID to query", hidden=True)
@click.option(
    "--info", "-i", is_flag=True, help="Retrieve detailed logging info", hidden=True
)
def logs(name, id, info):
    """
    Query logs for a flow run.

    Note: at least one of `name` or `id` must be specified. If only `name` is set then
    the most recent flow run with that name will be queried.


    \b
    Options:
        --name, -n      TEXT    A flow run name to query
        --id            TEXT    A flow run ID to query
        --info, -i              Retrieve detailed logging info
    """
    if not name and not id:
        click.secho("Either --name or --id must be provided", fg="red")
        return

    log_query = {
        with_args("logs", {"order_by": {EnumValue("timestamp"): EnumValue("asc")}}): {
            "timestamp": True,
            "message": True,
            "level": True,
        },
        "start_time": True,
    }
    if info:
        log_query = {
            with_args(
                "logs", {"order_by": {EnumValue("timestamp"): EnumValue("asc")}}
            ): {"timestamp": True, "info": True},
            "start_time": True,
        }

    query = {
        "query": {
            with_args(
                "flow_run",
                {
                    "where": {"name": {"_eq": name}, "id": {"_eq": id}},
                    "order_by": {EnumValue("start_time"): EnumValue("desc")},
                },
            ): log_query
        }
    }

    result = Client().graphql(query)

    flow_run = result.data.flow_run
    if not flow_run:
        click.secho("{} not found".format(name), fg="red")
        return

    run = flow_run[0]
    logs = run.logs
    output = []

    if not info:
        for log in logs:
            output.append([log.timestamp, log.level, log.message])

        click.echo(
            tabulate(
                output,
                headers=["TIMESTAMP", "LEVEL", "MESSAGE"],
                tablefmt="plain",
                numalign="left",
                stralign="left",
            )
        )
        return

    for log in logs:
        click.echo(log.info)
