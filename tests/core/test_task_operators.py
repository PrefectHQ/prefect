from prefect.core import Edge, Flow, Parameter, Task


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

        assert all([e in f.edges for e in [Edge(t1, t2), Edge(t2, t3), Edge(t3, t4)]])


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
