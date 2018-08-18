# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import prefect


class FlowRunnerTask(prefect.Task):
    def run(self, flow):
        prefect.context.run_flow(flow)
