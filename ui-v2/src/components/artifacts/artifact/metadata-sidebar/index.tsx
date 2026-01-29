import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { ArtifactSection } from "./artifact-section";
import { FlowRunSection } from "./flow-run-section";
import { LinksSection } from "./links-section";
import { TaskRunSection } from "./task-run-section";

export type MetadataSidebarProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const MetadataSidebar = ({ artifact }: MetadataSidebarProps) => {
	const { flow_run, task_run } = artifact;

	return (
		<div className="w-[250px] shrink-0 pt-4">
			<LinksSection artifact={artifact} />

			<ArtifactSection artifact={artifact} />

			{(flow_run || task_run) && <hr className="mt-4 border-border" />}

			{flow_run && <FlowRunSection flowRun={flow_run} />}

			{flow_run && task_run && <hr className="mt-4 border-border" />}

			{task_run && <TaskRunSection taskRun={task_run} />}
		</div>
	);
};
