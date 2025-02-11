import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { ArtifactSection } from "./artifact-section";
import { ConsolidatedTop } from "./consolidated-top";
import { FlowRunSection } from "./flow-run-section";
import { TaskRunSection } from "./task-run-section";

export type RightTableProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const RightTable = ({ artifact }: RightTableProps) => {
	const { flow_run, task_run } = artifact;

	return (
		<div className="m-r-2 pt-4" style={{ width: "250px" }}>
			{(artifact.key || flow_run || task_run) && (
				<ConsolidatedTop artifact={artifact} />
			)}

			<ArtifactSection artifact={artifact} />

			{(flow_run || task_run) && <hr className="mt-4" />}

			{flow_run && <FlowRunSection flowRun={flow_run} showHr={!!task_run} />}

			{task_run && <TaskRunSection taskRun={task_run} />}
		</div>
	);
};
