import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
import { Link } from "@tanstack/react-router";

export type ConsolidatedTopProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ConsolidatedTop = ({ artifact }: ConsolidatedTopProps) => {
	const { flow_run, task_run } = artifact;
	return (
		<div>
			{artifact.key && (
				<div>
					<Typography variant="bodySmall" className="text-muted-foreground">
						Artifact
					</Typography>
					<Link
						to={`/artifacts/key/$key`}
						params={{ key: artifact.key ?? "" }}
						className="text-blue-500 hover:underline"
					>
						<Typography variant="bodySmall">{artifact.key}</Typography>
					</Link>
				</div>
			)}
			{flow_run && (
				<div className="mt-2">
					<Typography variant="bodySmall" className="text-muted-foreground">
						Flow Run
					</Typography>
					<Link
						to={`/runs/flow-run/$id`}
						params={{ id: flow_run.id ?? "" }}
						className="text-blue-500 hover:underline"
					>
						<Typography variant="bodySmall">{flow_run.name}</Typography>
					</Link>
				</div>
			)}
			{task_run && (
				<div className="mt-2">
					<Typography variant="bodySmall" className="text-muted-foreground">
						Task Run
					</Typography>
					<Link
						to={`/runs/flow-run/$id`}
						params={{ id: task_run.id ?? "" }}
						className="text-blue-500 hover:underline"
					>
						<Typography variant="bodySmall">{task_run.name}</Typography>
					</Link>
				</div>
			)}
			<hr className="mt-4" />
		</div>
	);
};
