import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { ArtifactsKeyHeader } from "./artifacts-key-header";
import { TimelineContainer } from "./timeline/timelineContainer";

type ArtifactsKeyPageProps = {
	artifactKey: string;
	artifacts: ArtifactWithFlowRunAndTaskRun[];
};

export const ArtifactsKeyPage = ({
	artifactKey,
	artifacts,
}: ArtifactsKeyPageProps) => {
	return (
		<div>
			<ArtifactsKeyHeader
				artifactKey={artifactKey}
				pageHeader={artifacts[0]?.description ?? undefined}
			/>
			<TimelineContainer artifacts={artifacts} />
		</div>
	);
};
