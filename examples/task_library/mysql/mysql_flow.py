from prefect.tasks.mysql.mysql import MySQLFetch, MySQLExecute
from prefect import Flow, task

EXAMPLE_TABLE = "user"
HOST = "localhost"
PORT = 3306
DB_NAME = "ext"
USER = "admin"
PASSWORD = "admin"


mysql_fetch = MySQLFetch(
    host=HOST, port=PORT, db_name=DB_NAME, user=USER, password=PASSWORD
)

mysql_exec = MySQLExecute(
    host=HOST, port=PORT, db_name=DB_NAME, user=USER, password=PASSWORD
)


@task
def print_results(x):
    print(x)


with Flow("MySQL Example") as flow:
    # fetch 3 results
    fetch_results = mysql_fetch(
        query=f"SELECT * FROM {EXAMPLE_TABLE}", fetch="many", fetch_count=3
    )
    print_results(fetch_results)

    # execute a query that returns 3 results
    exec_results = mysql_exec(query=f"SELECT * FROM {EXAMPLE_TABLE} LIMIT 3")
    print_results(exec_results)


flow.run()
