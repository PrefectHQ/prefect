import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

export type ArtifactTimelineCardProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactTimelineCard = ({
	artifact,
}: ArtifactTimelineCardProps) => {
	const artifactTitle = useMemo(() => {
		return artifact.id?.split("-")[0];
	}, [artifact.id]);

	return (
		<Card
			data-testid={`timeline-card-${artifact.id}`}
			className="flex flex-col p-4 m-2 transition-transform hover:translate-x-2 grow"
		>
			<Link to="/artifacts/artifact/$id" params={{ id: artifact.id ?? "" }}>
				<Typography
					variant="body"
					className="font-bold text-blue-700 hover:underline"
				>
					{artifactTitle}
				</Typography>
			</Link>
			{artifact.flow_run && (
				<Typography variant="bodySmall">
					Flow run:{" "}
					<Link
						className="text-blue-700 hover:underline"
						to={"/runs/flow-run/$id"}
						params={{ id: artifact.flow_run_id ?? "" }}
					>
						{artifact.flow_run?.name}
					</Link>
				</Typography>
			)}
			{artifact.task_run && (
				<Typography variant="bodySmall">
					Task run:{" "}
					<Link
						className="text-blue-700 hover:underline"
						to={"/runs/task-run/$id"}
						params={{ id: artifact.task_run_id ?? "" }}
					>
						{artifact.task_run?.name}
					</Link>
				</Typography>
			)}
		</Card>
	);
};
