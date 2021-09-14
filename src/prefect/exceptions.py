from rich.traceback import Traceback


class PrefectError(Exception):
    pass


class MissingFlowError(PrefectError):
    pass


class UnspecifiedFlowError(PrefectError):
    pass


class FlowScriptError(PrefectError):
    def __init__(
        self,
        user_exc: Exception,
        script_path: str,
    ) -> None:
        message = f"Flow script at {script_path!r} encountered an exception"
        super().__init__(message)

        self.user_exc = user_exc

    def rich_user_traceback(self, **kwargs):
        trace = Traceback.extract(
            type(self.user_exc),
            self.user_exc,
            self.user_exc.__traceback__.tb_next.tb_next.tb_next.tb_next,
        )
        return Traceback(trace, **kwargs)


class PrefectSignal(BaseException):
    pass


class AbortSignal(PrefectSignal):
    pass
