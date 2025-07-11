import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { ArtifactDetailHeader } from "./artifact-detail-header";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";
import { DetailImage } from "./detail-image";
import { DetailMarkdown } from "./detail-markdown";
import { DetailProgress } from "./detail-progress";
import { DetailTable } from "./detail-table";

export type ArtifactDetailPageProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailPage = ({ artifact }: ArtifactDetailPageProps) => {
	const mapArtifactHoc = useMemo(() => {
		switch (artifact.type) {
			case "markdown":
			case "link":
				return <DetailMarkdown markdown={artifact.data as string} />;
			case "image":
				return <DetailImage url={artifact.data as string} />;
			case "progress":
				return <DetailProgress progress={artifact.data as number} />;
			case "table":
				return <DetailTable tableData={artifact.data as string} />;
			default:
				return <pre>{JSON.stringify(artifact.data, null, 2)}</pre>;
		}
	}, [artifact]);
	return (
		<div>
			<ArtifactDetailHeader artifact={artifact} />
			{mapArtifactHoc}
			<ArtifactDataDisplay artifact={artifact} />
		</div>
	);
};
