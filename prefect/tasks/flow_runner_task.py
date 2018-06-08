import prefect


class FlowRunnerTask(prefect.Task):
    def run(self, flow):
        prefect.context.run_flow(flow)
