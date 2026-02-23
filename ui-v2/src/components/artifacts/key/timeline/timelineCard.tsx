import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Card } from "@/components/ui/card";

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
				<p className="text-base font-bold text-link hover:text-link-hover hover:underline">
					{artifactTitle}
				</p>
			</Link>
			{artifact.flow_run && (
				<p className="text-sm">
					Flow run:{" "}
					<Link
						className="text-link hover:text-link-hover hover:underline"
						to={"/runs/flow-run/$id"}
						params={{ id: artifact.flow_run_id ?? "" }}
					>
						{artifact.flow_run?.name}
					</Link>
				</p>
			)}
			{artifact.task_run && (
				<p className="text-sm">
					Task run:{" "}
					<Link
						className="text-link hover:text-link-hover hover:underline"
						to={"/runs/task-run/$id"}
						params={{ id: artifact.task_run_id ?? "" }}
					>
						{artifact.task_run?.name}
					</Link>
				</p>
			)}
		</Card>
	);
};
