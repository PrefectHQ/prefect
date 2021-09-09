class PrefectError(Exception):
    pass


class MissingFlowError(PrefectError):
    pass


class UnspecifiedFlowError(PrefectError):
    pass


class FlowScriptError(PrefectError):
    pass
