import { Link } from "@tanstack/react-router";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { KeyValue } from "@/components/ui/key-value";

type LinksSectionProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const LinksSection = ({ artifact }: LinksSectionProps) => {
	const { flow_run, task_run } = artifact;
	const hasLinks = artifact.key || flow_run || task_run;

	if (!hasLinks) {
		return null;
	}

	return (
		<div className="flex flex-col gap-2">
			{artifact.key && (
				<KeyValue
					label="Artifact"
					value={
						<Link
							to="/artifacts/key/$key"
							params={{ key: artifact.key }}
							className="text-link hover:text-link-hover hover:underline"
						>
							{artifact.key}
						</Link>
					}
				/>
			)}

			{flow_run && (
				<KeyValue
					label="Flow Run"
					value={
						<Link
							to="/runs/flow-run/$id"
							params={{ id: flow_run.id }}
							className="text-link hover:text-link-hover hover:underline"
						>
							{flow_run.name}
						</Link>
					}
				/>
			)}

			{task_run && (
				<KeyValue
					label="Task Run"
					value={
						<Link
							to="/runs/task-run/$id"
							params={{ id: task_run.id }}
							className="text-link hover:text-link-hover hover:underline"
						>
							{task_run.name}
						</Link>
					}
				/>
			)}

			<hr className="mt-2 border-border" />
		</div>
	);
};
