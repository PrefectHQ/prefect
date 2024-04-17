async def run_task(
    task: Task,
    task_run: TaskRun = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
):
    """
    Runs a task against the API.
    """
    if not task_run:
        task_run = await create_task_run(...)  # dependency tracking set here

    # sets task run name
    # look up cache
    # set state to Running
    # preps logger
    async with set_run_context(...) as state:
        while state.is_running():
            try:
                result = await task.fn(*args, **kwargs)
                await finalize_run(
                    task_run, result
                )  # sets state to Completed, manages results
            except Exception as exc:
                # log it and set state to Failed
                state = await client.set_failed(...)
                if state.is_retrying():
                    # sleep relavent time period
                    await asyncio.sleep(0)

    return result


# task_run = TaskRun(...)
# task_run.init()
# task_run.finalize(result)
# task_run.enter_context()
