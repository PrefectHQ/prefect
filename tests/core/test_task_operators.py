from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.results import LocalResult
from prefect.tasks.core.operators import GetAttr
from prefect.utilities.collections import DotDict


class TestInteractionMethods:
    # -----------------------------------------
    # getattr

    def test_getattr_constant(self):
        with Flow(name="test") as f:
            z = GetAttr()(Parameter("x"), "b")
        state = f.run(parameters=dict(x=DotDict(a=1, b=2, c=3)))
        assert state.result[z].result == 2

    def test_getattr_default(self):
        with Flow(name="test") as f:
            x = Parameter("x")
            a = GetAttr(default="foo")(x, "missing")
            b = GetAttr()(x, "missing", "bar")
            c = GetAttr()(x, "missing", default="baz")
        state = f.run(parameters=dict(x=DotDict(a=1, b=2, c=3)))
        assert state.result[a].result == "foo"
        assert state.result[b].result == "bar"
        assert state.result[c].result == "baz"

    def test_getattr_missing(self):
        with Flow(name="test") as f:
            a = GetAttr()(Parameter("x"), "missing")
        state = f.run(parameters=dict(x=DotDict(a=1, b=2, c=3)))
        assert isinstance(state.result[a].result, AttributeError)

    def test_getattr_nested(self):
        with Flow(name="test") as f:
            z = GetAttr()(Parameter("x"), "a.b.c")
        state = f.run(parameters=dict(x=DotDict(a=DotDict(b=DotDict(c=1)))))
        assert state.result[z].result == 1

    def test_getattr_dynamic(self):
        with Flow(name="test") as f:
            z = GetAttr()(Parameter("x"), Parameter("y"))
        state = f.run(parameters=dict(x=DotDict(a=1, b=2, c=3), y="b"))
        assert state.result[z].result == 2

    def test_getattr_preserves_result_info(self):
        with Flow(name="test") as f:
            p = Parameter("p")
            z = GetAttr(checkpoint=False)(p, "foo")
            y = GetAttr(checkpoint=True, result=LocalResult(dir="home"))(p, "bar")

        assert z.checkpoint is False
        assert isinstance(y.result, LocalResult)
        assert y.result.dir.endswith("home")


class TestMagicInteractionMethods:
    # -----------------------------------------
    # getitem

    def test_getitem_list(self):
        with Flow(name="test") as f:
            z = Parameter("x")[Parameter("y")]
        state = f.run(parameters=dict(x=[1, 2, 3], y=1))
        assert state.result[z].result == 2

    def test_getitem_dict(self):
        with Flow(name="test") as f:
            z = Parameter("x")[Parameter("y")]
        state = f.run(parameters=dict(x=dict(a=1, b=2, c=3), y="b"))
        assert state.result[z].result == 2

    def test_getitem_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x")["b"]
        state = f.run(parameters=dict(x=dict(a=1, b=2, c=3)))
        assert state.result[z].result == 2

    def test_getitem_preserves_result_info(self):
        with Flow(name="test") as f:
            z = Task(checkpoint=False)()[0]
            y = Task(checkpoint=True, result=LocalResult(dir="home"))[1]

        assert z.checkpoint is False
        assert isinstance(y.result, LocalResult)
        assert y.result.dir.endswith("home")

    def test_getitem_name(self):
        with Flow(name="test") as f:
            x = Parameter("x")[0]
            assert x.name == "x[0]"
            y = Parameter("y")["a"]
            assert y.name == "y['a']"
            z = Parameter("z")[Parameter("a")]
            assert z.name == "z[a]"

    # -----------------------------------------
    # or / pipe / |

    def test_or(self):
        with Flow(name="test") as f:
            t1 = Task()
            t2 = Task()
            t1 | t2
        assert Edge(t1, t2) in f.edges

    def test_or_with_constant(self):
        with Flow(name="test") as f:
            t1 = Task()
            t1 | 1
        assert len(f.tasks) == 2
        assert len(f.edges) == 1

    def test_ror_with_constant(self):
        with Flow(name="test") as f:
            t1 = Task()
            1 | t1
        assert len(f.tasks) == 2
        assert len(f.edges) == 1

    # -----------------------------------------
    # Chain

    def test_chained_operators(self):
        with Flow(name="test") as f:
            t1 = Task("t1")
            t2 = Task("t2")
            t3 = Task("t3")
            t4 = Task("t4")
            t5 = Task("t5")
            t6 = Task("t6")

            (t1 | t2 | t3 | t4)

        assert all(e in f.edges for e in [Edge(t1, t2), Edge(t2, t3), Edge(t3, t4)])


class TestMagicOperatorMethods:
    # -----------------------------------------
    # addition

    def test_addition(self):
        with Flow(name="test") as f:
            z = Parameter("x") + Parameter("y")
        state = f.run(parameters=dict(x=1, y=2))
        assert state.result[z].result == 3

    def test_addition_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") + 10
        state = f.run(parameters=dict(x=1))
        assert state.result[z].result == 11

    def test_right_addition(self):
        with Flow(name="test") as f:
            z = 10 + Parameter("x")
        state = f.run(parameters=dict(x=1))
        assert state.result[z].result == 11

    # -----------------------------------------
    # subtraction

    def test_subtraction(self):
        with Flow(name="test") as f:
            z = Parameter("x") - Parameter("y")
        state = f.run(parameters=dict(x=1, y=2))
        assert state.result[z].result == -1

    def test_subtraction_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") - 10
        state = f.run(parameters=dict(x=1))
        assert state.result[z].result == -9

    def test_right_subtraction(self):
        with Flow(name="test") as f:
            z = 10 - Parameter("x")
        state = f.run(parameters=dict(x=1))
        assert state.result[z].result == 9

    # -----------------------------------------
    # multiplication

    def test_multiplication(self):
        with Flow(name="test") as f:
            z = Parameter("x") * Parameter("y")
        state = f.run(parameters=dict(x=2, y=3))
        assert state.result[z].result == 6

    def test_multiplication_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") * 10
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result == 20

    def test_right_multiplication(self):
        with Flow(name="test") as f:
            z = 10 * Parameter("x")
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result == 20

    # -----------------------------------------
    # division

    def test_division(self):
        with Flow(name="test") as f:
            z = Parameter("x") / Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result == 2.5

    def test_division_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") / 10
        state = f.run(parameters=dict(x=35))
        assert state.result[z].result == 3.5

    def test_right_division(self):
        with Flow(name="test") as f:
            z = 10 / Parameter("x")
        state = f.run(parameters=dict(x=4))
        assert state.result[z].result == 2.5

    # -----------------------------------------
    # floor division

    def test_floor_division(self):
        with Flow(name="test") as f:
            z = Parameter("x") // Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result == 2

    def test_floor_division_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") // 10
        state = f.run(parameters=dict(x=38))
        assert state.result[z].result == 3

    def test_right_floor_division(self):
        with Flow(name="test") as f:
            z = 10 // Parameter("x")
        state = f.run(parameters=dict(x=4))
        assert state.result[z].result == 2

    # -----------------------------------------
    # mod

    def test_mod(self):
        with Flow(name="test") as f:
            z = Parameter("x") % Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result == 1

    def test_mod_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") % 10
        state = f.run(parameters=dict(x=12))
        assert state.result[z].result == 2

    def test_right_mod(self):
        with Flow(name="test") as f:
            z = 10 % Parameter("x")
        state = f.run(parameters=dict(x=14))
        assert state.result[z].result == 10

    # -----------------------------------------
    # pow

    def test_pow(self):
        with Flow(name="test") as f:
            z = Parameter("x") ** Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result == 25

    def test_pow_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") ** 3
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result == 8

    def test_right_pow(self):
        with Flow(name="test") as f:
            z = 10 ** Parameter("x")
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result == 100

    # -----------------------------------------
    # gt

    def test_gt(self):
        with Flow(name="test") as f:
            z = Parameter("x") > Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is True

    def test_gt_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") > 3
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result is False

    def test_right_gt(self):
        with Flow(name="test") as f:
            z = 10 > Parameter("x")
        state = f.run(parameters=dict(x=10))
        assert state.result[z].result is False

    # -----------------------------------------
    # gte

    def test_gte(self):
        with Flow(name="test") as f:
            z = Parameter("x") >= Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is True

    def test_gte_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") >= 3
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result is False

    def test_right_gte(self):
        with Flow(name="test") as f:
            z = 10 >= Parameter("x")
        state = f.run(parameters=dict(x=10))
        assert state.result[z].result is True

    # -----------------------------------------
    # lt

    def test_lt(self):
        with Flow(name="test") as f:
            z = Parameter("x") < Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is False

    def test_lt_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") < 3
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result is True

    def test_right_lt(self):
        with Flow(name="test") as f:
            z = 10 < Parameter("x")
        state = f.run(parameters=dict(x=10))
        assert state.result[z].result is False

    # -----------------------------------------
    # lte

    def test_lte(self):
        with Flow(name="test") as f:
            z = Parameter("x") <= Parameter("y")
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is False

    def test_lte_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") <= 3
        state = f.run(parameters=dict(x=2))
        assert state.result[z].result is True

    def test_right_lte(self):
        with Flow(name="test") as f:
            z = 10 <= Parameter("x")
        state = f.run(parameters=dict(x=10))
        assert state.result[z].result is True

    # -----------------------------------------
    # and

    def test_and(self):
        with Flow(name="test") as f:
            z = Parameter("x") & Parameter("y")
        state = f.run(parameters=dict(x=True, y=False))
        assert state.result[z].result is False

        state = f.run(parameters=dict(x=True, y=True))
        assert state.result[z].result is True

        state = f.run(parameters=dict(x=False, y=True))
        assert state.result[z].result is False

        state = f.run(parameters=dict(x=False, y=False))
        assert state.result[z].result is False

    def test_and_with_constant(self):
        with Flow(name="test") as f:
            z = Parameter("x") & True
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is False

        with Flow(name="test") as f:
            z = Parameter("x") & False
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is False

    def test_right_and(self):
        with Flow(name="test") as f:
            z = True & Parameter("x")
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is False
        with Flow(name="test") as f:
            z = False & Parameter("x")
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is False


class TestNonMagicOperatorMethods:
    def test_equals(self):
        with Flow(name="test") as f:
            z = Parameter("x").is_equal(Parameter("y"))
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=5, y=5))
        assert state.result[z].result is True

    def test_not_equals(self):
        with Flow(name="test") as f:
            z = Parameter("x").is_not_equal(Parameter("y"))
        state = f.run(parameters=dict(x=5, y=2))
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=5, y=5))
        assert state.result[z].result is False

    def test_not(self):
        with Flow(name="test") as f:
            z = Parameter("x").not_()
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is True

    def test_or(self):
        with Flow(name="test") as f:
            z = Parameter("x").or_(False)
        state = f.run(parameters=dict(x=True))
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=False))
        assert state.result[z].result is False
