import datetime
from pydantic import Field
from typing import Dict, List, Any
import prefect
from prefect.utilities.serialization_future import PolymorphicSerializable

from typing import Dict, List, Callable, Union


class Result(PolymorphicSerializable):
    class Config:
        extra = "allow"

    # for ALL results
    location: str = None

    # for SafeResults
    value: Union[List, Dict, float, bool, int, str] = None

    # Azure
    container: str = None

    # GCS, S3
    bucket: str = None

    # Local
    dir: str = None

    # Secret
    secret_type: Callable = None

    @classmethod
    def from_result(cls, obj: prefect.engine.result.base.Result) -> "Result":
        return super()._from_object(obj)

    def to_result(self):
        return super()._to_object()


class State(PolymorphicSerializable):

    # for ALL states
    message: str = None
    result: Result = None
    context: Dict[str, Any] = Field(default_factory=dict)
    cached_inputs: Dict[str, Any] = Field(default_factory=dict)

    # for SCHEDULED states
    start_time: datetime.datetime = None

    # for METASTATE states
    state: "State" = None

    # for RETRYING states
    run_count: int = None

    # for LOOPED states
    loop_count: int = None

    # for CACHED states
    cached_parameters: Dict[str, Any] = None
    cached_result_expiration: datetime.datetime = None

    # for backwards compatibility
    # backwards_compatible_result: dict = Field(alias='_result')

    @classmethod
    def from_state(cls, state: prefect.engine.state.State) -> "State":
        return super()._from_object(obj=state, result=Result.from_result(state._result))

    def to_state(self):
        # if self.backwards_compatible_result is not None:
        #     result = self.backwards_compatible_result
        # else:
        result = self.result.to_result()
        return super()._to_object(result=result)


State.update_forward_refs()
