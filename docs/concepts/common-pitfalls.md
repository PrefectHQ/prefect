# Common Pitfalls

## Serialization

Most of the underlying communication patterns within Prefect require that objects can be _serialized_ into some format (typically, JSON or binary).  For example, when a task returns a data payload, the result 
