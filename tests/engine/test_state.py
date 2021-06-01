import datetime
import json
from threading import RLock

import pendulum
import cloudpickle
import pytest

import prefect
from prefect.engine.result import Result, NoResult
from prefect.engine.results import PrefectResult
from prefect.engine.state import (
    Cancelled,
    Cached,
    ClientFailed,
    Failed,
    Finished,
    Looped,
    Mapped,
    Paused,
    Pending,
    Queued,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Submitted,
    Success,
    TimedOut,
    TriggerFailed,
    ValidationFailed,
    _MetaState,
)
from prefect.serialization.state import StateSchema

all_states = sorted(
    set(
        cls
        for cls in prefect.engine.state.__dict__.values()
        if isinstance(cls, type)
        and issubclass(cls, prefect.engine.state.State)
        and not cls is _MetaState
    ),
    key=lambda c: c.__name__,
)


class TestCreateStates:
    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_no_args(self, cls):
        state = cls()
        assert state.message is None
        assert state.result is None
        assert state._result == NoResult
        assert state.context == dict()
        assert state.cached_inputs == dict()

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_kwarg_result_arg(self, cls):
        state = cls(result=1)
        assert isinstance(state._result, Result)
        assert state.result == 1
        assert state.message is None
        assert isinstance(state._result, Result)

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_kwarg_cached_inputs(self, cls):
        state = cls(cached_inputs=dict(x=42))
        assert state.message is None
        assert state.cached_inputs == dict(x=42)

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_kwarg_context(self, cls):
        state = cls(context={"my-keys": "my-vals"})
        assert state.message is None
        assert state.context == {"my-keys": "my-vals"}

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_fully_hydrated_result(self, cls):
        result = Result(value=10)
        state = cls(result=result)
        assert isinstance(state._result, Result)
        assert state._result.value == 10
        assert state.result == 10

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_positional_message_arg(self, cls):
        state = cls("i am a string")
        assert state.message == "i am a string"
        assert state.result is None
        assert state._result == NoResult

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_data_and_message(self, cls):
        state = cls(message="x", result="y")
        assert state.result == "y"
        assert state.message == "x"

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_data_and_error(self, cls):
        try:
            1 / 0
        except Exception as e:
            state = cls(result="oh no!", message=e)
        assert state.result == "oh no!"
        assert isinstance(state.message, Exception)
        assert "division by zero" in str(state.message)

    @pytest.mark.parametrize("cls", all_states)
    def test_create_state_with_tags_in_context(self, cls):
        with prefect.context(task_tags=set("abcdef")):
            state = cls()
        assert state.message is None
        assert state.result is None
        assert state._result == NoResult
        assert state.context == dict(tags=list(set("abcdef")))

        with prefect.context(task_tags=set("abcdef")):
            state = cls(context={"tags": ["foo"]})
        assert state.context == dict(tags=["foo"])


def test_repr_with_message():
    state = Success(message="a message")
    assert repr(state) == '<Success: "a message">'


def test_repr_without_message():
    state = Success()
    assert state.message is None
    assert repr(state) == "<Success>"


def test_scheduled_states_have_default_times():
    now = pendulum.now("utc")
    assert now - Scheduled().start_time < datetime.timedelta(seconds=0.1)
    assert now - Retrying().start_time < datetime.timedelta(seconds=0.1)


def test_paused_state_has_no_default_start_time():
    state = Paused()
    assert state.start_time is None


def test_passing_none_to_paused_state_has_no_default_start_time():
    state = Paused(start_time=None)
    assert state.start_time is None


def test_paused_state_can_have_start_time():
    dt = pendulum.now().add(years=1)
    state = Paused(start_time=dt)
    assert state.start_time == dt


def test_queued_states_have_start_times():
    now = pendulum.now("utc")
    assert now - Queued().start_time < datetime.timedelta(seconds=0.1)


def test_queued_states_accept_start_times():
    st = pendulum.datetime(2050, 1, 1)
    state = Queued(start_time=st)
    assert state.start_time == st


@pytest.mark.parametrize("cls", all_states)
def test_only_scheduled_and_queued_states_have_start_times(cls):
    """
    the start_time attribute of a scheduled state is important and used (outside Python)
    to identify when a state is scheduled
    """
    state = cls()
    if hasattr(state, "start_time"):
        assert isinstance(state, Scheduled) or isinstance(state, Queued)
        if isinstance(state, Scheduled):
            assert state.is_scheduled()
    else:
        assert not isinstance(state, Scheduled)
        assert not state.is_scheduled()


@pytest.mark.parametrize("cls", all_states)
def test_only_scheduled_states_have_task_run_count_in_context(cls):
    """
    Storing task_run_count in state.context provides a way of communicating
    the current run_count across multiple state changes.  Persisting this data
    in a Finished state causes the run count to "freeze" across runs.
    """
    with prefect.context(task_run_count=910):
        state = cls()

    if state.context.get("task_run_count") is not None:
        assert isinstance(state, Scheduled)
        assert state.is_scheduled()
        assert state.context["task_run_count"] == 910
    else:
        assert not isinstance(state, Scheduled)


def test_retry_stores_loop_count():
    state = Looped(loop_count=2)
    assert state.loop_count == 2


def test_looped_stores_default_loop_count():
    state = Looped()
    assert state.loop_count == 1


def test_looped_stores_default_loop_count_in_context():
    with prefect.context(task_loop_count=5):
        state = Looped()
    assert state.loop_count == 5


def test_retry_stores_run_count():
    state = Retrying(run_count=2)
    assert state.run_count == 2


def test_retry_stores_default_run_count():
    state = Retrying()
    assert state.run_count == 1


def test_retry_stores_default_run_count_in_context():
    with prefect.context(task_run_count=5):
        state = Retrying()
    assert state.run_count == 5


@pytest.mark.parametrize("cls", all_states)
def test_states_have_color(cls):
    assert cls.color.startswith("#")


def test_serialize_and_deserialize_on_raw_cached_state():
    now = pendulum.now("utc")
    state = Cached(
        cached_inputs=dict(x=PrefectResult(value=99), p=PrefectResult(value="p")),
        result=dict(hi=5, bye=6),
        cached_result_expiration=now,
    )
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, Cached)
    assert new_state.color == state.color
    assert new_state.result is None
    assert new_state.cached_result_expiration == state.cached_result_expiration
    assert new_state.cached_inputs == dict.fromkeys(["x", "p"], PrefectResult())


def test_serialize_and_deserialize_on_mixed_cached_state():
    safe_dct = PrefectResult(location=json.dumps(dict(hi=5, bye=6)))
    now = pendulum.now("utc")
    state = Cached(
        cached_inputs=dict(x=PrefectResult(value=2), p=PrefectResult(value="p")),
        result=safe_dct,
        cached_result_expiration=now,
    )
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, Cached)
    assert new_state.color == state.color
    assert new_state._result.location == json.dumps(dict(hi=5, bye=6))
    assert new_state.cached_result_expiration == state.cached_result_expiration
    assert new_state.cached_inputs == dict.fromkeys(["x", "p"], PrefectResult())


def test_state_equality():
    assert State() == State()
    assert Success() == Success()
    assert Success(result=1) == Success(result=1)
    assert not State() == Success()
    assert not Success(result=1) == Success(result=2)
    assert Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(x=1))
    assert not Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(x=2))
    assert not Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(y=1))


def test_state_equality_ignores_context():
    s, r = State(result=1), State(result=1)
    s.context["key"] = "value"
    assert s == r


def test_state_equality_ignores_message():
    assert State(result=1, message="x") == State(result=1, message="y")
    assert State(result=1, message="x") != State(result=2, message="x")


def test_state_equality_with_nested_states():
    s1 = State(result=Success(result=1))
    s2 = State(result=Success(result=2))
    s3 = State(result=Success(result=1))
    assert s1 != s2
    assert s1 == s3


def test_states_are_hashable():
    assert {State(), Pending(), Success()}


def test_states_with_mutable_attrs_are_hashable():
    assert {State(result=[1]), Pending(cached_inputs=dict(a=1))}


@pytest.mark.parametrize("cls", [s for s in all_states if s is not State])
def test_serialize_method(cls):
    serialized = cls().serialize()
    assert isinstance(serialized, dict)
    assert isinstance(prefect.serialization.state.StateSchema().load(serialized), cls)


class TestStateHierarchy:
    def test_scheduled_is_pending(self):
        assert issubclass(Scheduled, Pending)

    def test_resume_is_scheduled(self):
        assert issubclass(Resume, Scheduled)

    def test_mapped_is_success(self):
        assert issubclass(Mapped, Success)

    def test_cached_is_successful(self):
        assert issubclass(Cached, Success)

    def test_retrying_is_pending(self):
        assert issubclass(Retrying, Pending)

    def test_retrying_is_scheduled(self):
        assert issubclass(Retrying, Scheduled)

    def test_looped_is_finished(self):
        assert issubclass(Looped, Finished)

    def test_success_is_finished(self):
        assert issubclass(Success, Finished)

    def test_failed_is_finished(self):
        assert issubclass(Failed, Finished)

    def test_cancelled_is_failed(self):
        assert issubclass(Cancelled, Finished)

    def test_trigger_failed_is_finished(self):
        assert issubclass(TriggerFailed, Finished)

    def test_timedout_is_finished(self):
        assert issubclass(TimedOut, Finished)

    def test_skipped_is_finished(self):
        assert issubclass(Skipped, Finished)

    def test_skipped_is_success(self):
        assert issubclass(Skipped, Success)

    def test_timedout_is_failed(self):
        assert issubclass(TimedOut, Failed)

    def test_trigger_failed_is_failed(self):
        assert issubclass(TriggerFailed, Failed)

    def test_validation_failed_is_failed(self):
        assert issubclass(ValidationFailed, Failed)

    def test_paused_is_scheduled(self):
        assert issubclass(Paused, Scheduled)


@pytest.mark.parametrize(
    "state_check",
    [
        dict(state=Cancelled(), assert_true={"is_finished"}),
        dict(state=Cached(), assert_true={"is_cached", "is_finished", "is_successful"}),
        dict(state=ClientFailed(), assert_true={"is_meta_state"}),
        dict(state=Failed(), assert_true={"is_finished", "is_failed"}),
        dict(state=Finished(), assert_true={"is_finished"}),
        dict(state=Looped(), assert_true={"is_finished", "is_looped"}),
        dict(state=Mapped(), assert_true={"is_finished", "is_mapped", "is_successful"}),
        dict(state=Paused(), assert_true={"is_pending", "is_scheduled"}),
        dict(state=Pending(), assert_true={"is_pending"}),
        dict(
            state=Queued(), assert_true={"is_meta_state", "is_queued", "is_scheduled"}
        ),
        dict(state=Resume(), assert_true={"is_pending", "is_scheduled"}),
        dict(
            state=Retrying(), assert_true={"is_pending", "is_scheduled", "is_retrying"}
        ),
        dict(state=Running(), assert_true={"is_running"}),
        dict(state=Scheduled(), assert_true={"is_pending", "is_scheduled"}),
        dict(
            state=Skipped(), assert_true={"is_finished", "is_successful", "is_skipped"}
        ),
        dict(state=Submitted(), assert_true={"is_meta_state", "is_submitted"}),
        dict(state=Success(), assert_true={"is_finished", "is_successful"}),
        dict(state=TimedOut(), assert_true={"is_finished", "is_failed"}),
        dict(state=TriggerFailed(), assert_true={"is_finished", "is_failed"}),
        dict(state=ValidationFailed(), assert_true={"is_finished", "is_failed"}),
    ],
)
def test_state_is_methods(state_check):
    """
    Iterates over all of the "is_*()" methods of the state, asserting that each one is
    False, unless the name of that method is provided as `assert_true`.

    For example, if `state_check == (Pending(), {'is_pending'})`, then this method will
    assert that `state.is_running()` is False, `state.is_successful()` is False, etc. but
    `state.is_pending()` is True.
    """
    state = state_check["state"]
    assert_true = state_check["assert_true"]

    for attr in dir(state):
        if attr.startswith("is_") and callable(getattr(state, attr)):
            if attr in assert_true:
                assert getattr(state, attr)()
            else:
                assert not getattr(state, attr)()


@pytest.mark.parametrize("include_self", [True, False])
def test_children_method_on_base_state(include_self):
    all_states_set = set(all_states)
    if not include_self:
        all_states_set.remove(State)
    assert all_states_set == set(State.children(include_self=include_self))


def test_children_method_on_leaf_state_returns_empty():
    assert TriggerFailed.children() == []


def test_children_method_names_only_returns_strings():
    assert TriggerFailed.children(include_self=True, names_only=True) == [
        "TriggerFailed"
    ]


@pytest.mark.parametrize("include_self", [True, False])
def test_children_method_on_success(include_self):
    expected = {Cached, Mapped, Skipped}
    if include_self:
        expected.add(Success)
    assert set(Success.children(include_self=include_self)) == expected


@pytest.mark.parametrize("include_self", [True, False])
def test_parent_method_on_base_state(include_self):
    assert State.parents(include_self=include_self) == ([State] if include_self else [])


@pytest.mark.parametrize("include_self", [True, False])
def test_parent_method_on_base_state_names_only(include_self):
    assert State.parents(include_self=include_self, names_only=True) == (
        ["State"] if include_self else []
    )


@pytest.mark.parametrize("include_self", [True, False])
def test_children_method_on_leaf_state_returns_hierarchy(include_self):
    expected = {Finished, Failed, State}
    if include_self:
        expected.add(TriggerFailed)
    assert set(TriggerFailed.parents(include_self=include_self)) == expected


def test_parents_method_on_success():
    assert set(Success.parents()) == {Finished, State}


class TestResultInterface:
    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_result_calls_read(self, cls):
        """
        This test ensures that the read logic of the provided result is
        used instead of self._result; this is important when "hydrating" JSON
        representations of Results objects that come from Cloud.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = 42
                return self

        state = cls(result=Result(location=""))
        assert state.message is None
        assert state.result is None

        new_state = state.load_result(MyResult(location=""))
        # mapped states should never attempt to hydrate their results
        # the Result interface is _not_ used for Mapped state results, only their children
        if not new_state.is_mapped():
            assert new_state.result == 42
            assert new_state._result.location == "foo"
        else:
            assert new_state.result is None
            assert not new_state._result.location

    def test_state_load_result_loads_map_states(self):
        """
        This test ensures that loading state results also loads mapped children results.
        See https://github.com/PrefectHQ/prefect/pull/2952
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                new = self.copy()
                new.value = kwargs.get("location", args[0])
                return new

        state = Mapped(
            map_states=[
                None,
                Success("1", result=MyResult(location="foo")),
                Success("2", result=MyResult(location="bar")),
            ]
        )
        assert state.message is None
        assert state.result is None
        assert [getattr(s, "result", None) for s in state.map_states] == [None] * 3

        new_state = state.load_result(MyResult(location=""))
        assert new_state.result == [None, "foo", "bar"]
        assert not new_state._result.location
        assert [getattr(s, "result", None) for s in state.map_states] == [
            None,
            "foo",
            "bar",
        ]

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_result_doesnt_call_read_if_value_present(self, cls):
        """
        This test ensures that multiple calls to `load_result` will not result in
        multiple redundant reads from the remote result location.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = "bar"
                return self

        state = cls(result=Result(value=42))
        assert state.message is None
        assert state.result == 42

        new_state = state.load_result(MyResult())
        assert new_state.result == 42
        assert new_state._result.location is None

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_result_doesnt_call_read_if_location_is_none(self, cls):
        """
        If both the value and location information are None, we assume that None is the
        correct return value and perform no action.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = "bar"
                return self

        state = cls(result=Result())
        assert state.message is None
        assert state.result is None
        assert state._result.location is None

        new_state = state.load_result(MyResult())
        assert new_state.message is None
        assert new_state.result is None
        assert new_state._result.location is None

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_cached_results_calls_read(self, cls):
        """
        This test ensures that the read logic of the provided result is
        used instead of self._result; this is important when "hydrating" JSON
        representations of Results objects that come from Cloud.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = 42
                return self

        state = cls(cached_inputs=dict(x=Result()))
        new_state = state.load_cached_results(dict(x=MyResult(location="")))

        assert new_state.cached_inputs["x"].value == 42
        assert new_state.cached_inputs["x"].location == "foo"

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_cached_results_doesnt_call_read_if_value_present(self, cls):
        """
        This test ensures that multiple calls to `load_result` will not result in
        multiple redundant reads from the remote result location.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = "bar"
                return self

        state = cls(cached_inputs=dict(x=Result(value=42)))

        new_state = state.load_cached_results(dict(x=MyResult()))
        assert new_state.cached_inputs["x"].value == 42
        assert new_state.cached_inputs["x"].location is None

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_cached_results_doesnt_call_read_if_location_is_none(self, cls):
        """
        If both the value and location information are None, we assume that None is the
        correct return value and perform no action.
        """

        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.location = "foo"
                self.value = "bar"
                return self

        state = cls(cached_inputs=dict(x=Result()))
        new_state = state.load_cached_results(dict(x=MyResult()))
        assert new_state.cached_inputs["x"].value is None
        assert new_state.cached_inputs["x"].location is None

    @pytest.mark.parametrize("cls", all_states)
    def test_state_load_cached_results_reads_if_location_is_provided(self, cls):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.value = "bar"
                return self

        state = cls(cached_inputs=dict(y=Result()))
        new_state = state.load_cached_results(dict(y=MyResult(location="foo")))
        assert new_state.cached_inputs["y"].value == "bar"
        assert new_state.cached_inputs["y"].location == "foo"


def test_meta_states_dont_nest():
    state = Queued(state=Pending())

    for i in range(300):
        if i % 2:
            state = Queued(state=state)
        else:
            state = Submitted(state=state)

    assert state.state.is_pending()
    assert not state.state.is_meta_state()

    new_state = StateSchema().load(state.serialize())
    assert new_state.is_meta_state()
    assert not new_state.state.is_meta_state()


def test_n_map_states():
    state = Mapped(map_states=[1, 2])
    assert state.n_map_states == 2

    state = Mapped(n_map_states=4)
    assert state.n_map_states == 4

    state = Mapped(map_states=[1, 2], n_map_states=4)
    assert state.n_map_states == 4


def test_init_with_falsey_value():
    state = Success(result={})
    assert state.result == {}


def test_state_pickle():
    class Data:
        def __init__(self, foo: int = 1, bar: str = "") -> None:
            self.foo = foo
            self.bar = bar

        def __eq__(self, o: object) -> bool:
            return o.bar == self.bar and o.foo == self.foo

    state = State(message="message", result=Data(bar="bar"))
    new_state = cloudpickle.loads(cloudpickle.dumps(state))

    assert state.message == new_state.message  # message not included in __eq__
    assert state == new_state


def test_state_pickle_with_unpicklable_result_raises():
    state = State(result=RLock())  # An unpickable result type
    with pytest.raises(TypeError, match="pickle"):
        cloudpickle.dumps(state)


def test_state_pickle_with_unpicklable_result_raises_when_not_from_cloudpickle():
    # This test covers the case where the exception during pickle does not come from
    # cloudpickle
    class AtypicalUnpickableData:
        def __getstate__(self):
            raise TypeError("Foo!")

    state = State(result=AtypicalUnpickableData())
    with pytest.raises(TypeError, match="Foo"):
        cloudpickle.dumps(state)


def test_state_pickle_with_exception():
    state = State(result=Exception("foo"))
    new_state = cloudpickle.loads(cloudpickle.dumps(state))

    assert isinstance(new_state.result, Exception)
    assert new_state.result.args == ("foo",)


def test_state_pickle_with_unpicklable_exception_converts_to_repr():
    class UnpicklableException(Exception):
        def __init__(self, *args) -> None:
            self.lock = RLock()
            super().__init__(*args)

    state = State(result=UnpicklableException())
    new_state = cloudpickle.loads(cloudpickle.dumps(state))

    # Get the pickle error directly -- this is robust to changes across python versions
    pickle_exc = None
    try:
        cloudpickle.dumps(UnpicklableException())
    except Exception as exc:
        pickle_exc = exc

    # Cast to a string
    assert isinstance(new_state.result, str)
    # Includes the repr of our exception result
    assert repr(UnpicklableException()) in new_state.result
    # Includes context for the exception
    assert "The following exception could not be pickled" in new_state.result
    # Includes pickle error
    assert repr(pickle_exc) in new_state.result

    # Does not alter the original object
    assert isinstance(state.result, UnpicklableException)
