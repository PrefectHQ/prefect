import { Link } from "@tanstack/react-router";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";

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
		<div>
			{artifact.key && (
				<div>
					<Typography variant="bodySmall" className="text-muted-foreground">
						Artifact
					</Typography>
					<Link
						to="/artifacts/key/$key"
						params={{ key: artifact.key }}
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
						to="/runs/flow-run/$id"
						params={{ id: flow_run.id }}
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
						to="/runs/task-run/$id"
						params={{ id: task_run.id }}
						className="text-blue-500 hover:underline"
					>
						<Typography variant="bodySmall">{task_run.name}</Typography>
					</Link>
				</div>
			)}

			<hr className="mt-4 border-border" />
		</div>
	);
};
