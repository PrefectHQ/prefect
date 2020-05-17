import datetime
import json
import tempfile
import uuid

import cloudpickle
import pendulum
import pytest

import prefect
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.results import PrefectResult
from prefect.engine.result_handlers import JSONResultHandler, LocalResultHandler
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
from prefect.serialization.result_handlers import ResultHandlerSchema
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


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_no_args(cls):
    state = cls()
    assert state.message is None
    assert state.result is None
    assert state._result == NoResult
    assert state.context == dict()
    assert state.cached_inputs == dict()


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_kwarg_result_arg(cls):
    state = cls(result=1)
    assert isinstance(state._result, Result)
    assert state._result.safe_value is NoResult
    assert state._result.result_handler is None
    assert state.result == 1
    assert state.message is None
    assert isinstance(state._result, Result)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_kwarg_cached_inputs(cls):
    state = cls(cached_inputs=dict(x=42))
    assert state.message is None
    assert state.cached_inputs == dict(x=42)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_kwarg_context(cls):
    state = cls(context={"my-keys": "my-vals"})
    assert state.message is None
    assert state.context == {"my-keys": "my-vals"}


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_fully_hydrated_result(cls):
    result = Result(value=10)
    state = cls(result=result)
    assert isinstance(state._result, Result)
    assert state._result.value == 10
    assert state.result == 10


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_positional_message_arg(cls):
    state = cls("i am a string")
    assert state.message == "i am a string"
    assert state._result == NoResult


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_data_and_message(cls):
    state = cls(message="x", result="y")
    assert state.result == "y"
    assert state.message == "x"


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_data_and_error(cls):
    try:
        1 / 0
    except Exception as e:
        state = cls(result="oh no!", message=e)
    assert state.result == "oh no!"
    assert isinstance(state.message, Exception)
    assert "division by zero" in str(state.message)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_tags_in_context(cls):
    with prefect.context(task_tags=set("abcdef")):
        state = cls()
    assert state.message is None
    assert state.result is None
    assert state._result == NoResult
    assert state.context == dict(tags=list(set("abcdef")))

    with prefect.context(task_tags=set("abcdef")):
        state = cls(context={"tags": ["foo"]})
    assert state.context == dict(tags=["foo"])


def test_scheduled_states_have_default_times():
    now = pendulum.now("utc")
    assert now - Scheduled().start_time < datetime.timedelta(seconds=0.1)
    assert now - Retrying().start_time < datetime.timedelta(seconds=0.1)


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
        assert not state.is_scheduled()


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


def test_serialize_and_deserialize_on_safe_cached_state():
    safe = SafeResult("99", result_handler=JSONResultHandler())
    safe_dct = SafeResult(dict(hi=5, bye=6), result_handler=JSONResultHandler())
    now = pendulum.now("utc")
    state = Cached(
        cached_inputs=dict(x=safe, p=safe),
        result=safe_dct,
        cached_result_expiration=now,
    )
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, Cached)
    assert new_state.color == state.color
    assert new_state.result == dict(hi=5, bye=6)
    assert new_state.cached_result_expiration == state.cached_result_expiration
    assert new_state.cached_inputs == state.cached_inputs


@pytest.mark.parametrize("cls", [s for s in all_states if s.__name__ != "State"])
def test_serialization_of_cached_inputs_with_safe_values(cls):
    safe5 = SafeResult(5, result_handler=JSONResultHandler())
    state = cls(cached_inputs=dict(hi=safe5, bye=safe5))
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, cls)
    assert new_state.cached_inputs == state.cached_inputs


@pytest.mark.parametrize("cls", [s for s in all_states if s.__name__ != "State"])
def test_serialization_of_cached_inputs_with_unsafe_values(cls):
    unsafe5 = PrefectResult(value=5)
    state = cls(cached_inputs=dict(hi=unsafe5, bye=unsafe5))
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, cls)
    assert new_state.cached_inputs == dict(hi=PrefectResult(), bye=PrefectResult())


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
        dict(state=Queued(), assert_true={"is_meta_state", "is_queued"}),
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


def test_children_method_on_base_state():
    all_states_set = set(all_states)
    all_states_set.remove(State)
    assert all_states_set == set(State.children())


def test_children_method_on_leaf_state_returns_empty():
    assert TriggerFailed.children() == []


def test_children_method_on_success():
    expected = {Cached, Mapped, Skipped}
    assert set(Success.children()) == expected


def test_parent_method_on_base_state():
    assert State.parents() == []


def test_children_method_on_leaf_state_returns_hierarchy():
    assert set(TriggerFailed.parents()) == {Finished, Failed, State}


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
        assert new_state.result == 42
        assert new_state._result.location == "foo"

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
    def test_state_load_result_reads_if_location_is_provided(self, cls):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.value = "bar"
                return self

        state = cls(result=Result())
        assert state.message is None
        assert state.result is None
        assert state._result.location is None

        new_state = state.load_result(MyResult(location="foo"))
        assert new_state.message is None
        assert new_state.result == "bar"
        assert new_state._result.location == "foo"

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
