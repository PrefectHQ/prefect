from prefect.tasks.fugue import fsql, transform
from prefect.tasks.fugue.tasks import _normalize_yields, _truncate_name
from pytest import raises
from prefect import Flow, task, Parameter
from typing import List, Any
from fugue import NativeExecutionEngine, parse_execution_engine


def test_fsql():
    # simplest case
    with Flow("test") as flow:
        result = fsql("""CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x""")
        wf_assert(result, lambda dfs: dfs["x"].as_array() == [[0]])
    assert flow.run().is_successful()

    # with simple parameter
    with Flow("test") as flow:
        result = fsql("""CREATE [[{{x}}]] SCHEMA a:int YIELD DATAFRAME AS x""", x=0)
        wf_assert(result, lambda dfs: dfs["x"].as_array() == [[0]])
    assert flow.run().is_successful()

    # with Prefect parameter
    with Flow("test") as flow:
        x = Parameter("x")
        result = fsql("""CREATE [[{{x}}]] SCHEMA a:int YIELD DATAFRAME AS x""", x=x)
        wf_assert(result, lambda dfs: dfs["x"].as_array() == [[1]])
    assert flow.run({"x": 1}).is_successful()

    # with df parameter
    with Flow("test") as flow:
        d = Parameter("d")
        result1 = fsql("""CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x""")
        # pass result1 as yields
        result2 = fsql(
            """SELECT a+{{d}} AS a FROM x YIELD DATAFRAME AS y""", result1, d=d
        )
        # pass the specific dataframe
        result3 = fsql("""SELECT * FROM df YIELD DATAFRAME AS y""", df=result1["x"])
        wf_assert(result2, lambda dfs: dfs["y"].as_array() == [[1]])
        wf_assert(result3, lambda dfs: dfs["y"].as_array() == [[0]])
    assert flow.run({"d": 1}).is_successful()


def test_transform():
    def t1(df: List[List[Any]]) -> List[List[Any]]:
        return df

    # schema: *
    def t2(df: List[List[Any]]) -> List[List[Any]]:
        return df

    # simplest case
    with Flow("test") as flow:
        dfs = fsql("""CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x""")

        result = transform(dfs["x"], t1, schema="*", force_output_fugue_dataframe=True)
        wf_assert(result, lambda df: df.as_array() == [[0]])

        result = transform(dfs["x"], t2, force_output_fugue_dataframe=True)
        wf_assert(result, lambda df: df.as_array() == [[0]])

    assert flow.run().is_successful()

    @task
    def provide_func():
        return t2

    @task
    def provide_schema():
        return "*"

    # with dependency
    with Flow("test") as flow:
        dfs = fsql("""CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x""")

        result = transform(
            dfs["x"], t1, schema=provide_schema(), force_output_fugue_dataframe=True
        )
        wf_assert(result, lambda df: df.as_array() == [[0]])

        result = transform(dfs["x"], provide_func(), force_output_fugue_dataframe=True)
        wf_assert(result, lambda df: df.as_array() == [[0]])

    assert flow.run().is_successful()


def test_truncate_name():
    raises(ValueError, lambda: _truncate_name(None))
    assert _truncate_name("abc") == "abc"


def test_normalize_yields():
    assert _normalize_yields(1) == [1]
    assert _normalize_yields(None) == []
    assert _normalize_yields((1, 2)) == [1, 2]
    assert _normalize_yields([1, 2]) == [1, 2]


@task
def wf_assert(data, validator) -> None:
    print(validator(data))
    assert validator(data)
