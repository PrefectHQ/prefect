import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { LayoutWellSidebar } from "@/components/ui/layout-well";
import { ArtifactDetailHeader } from "./artifact-detail-header";
import { ArtifactDetailTabs } from "./artifact-detail-tabs";
import { DetailImage } from "./detail-image";
import { DetailMarkdown } from "./detail-markdown";
import { DetailProgress } from "./detail-progress";
import { DetailTable } from "./detail-table";
import { MetadataSidebar } from "./metadata-sidebar";

export type ArtifactDetailPageProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailPage = ({ artifact }: ArtifactDetailPageProps) => {
	const artifactContent = useMemo(() => {
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

	const sidebarContent = <MetadataSidebar artifact={artifact} />;

	return (
		<div className="flex flex-col gap-4">
			<ArtifactDetailHeader artifact={artifact} />
			<div className="flex flex-col lg:flex-row lg:gap-6">
				<div className="flex-1 min-w-0">
					<ArtifactDetailTabs
						artifact={artifact}
						artifactContent={artifactContent}
						detailsContent={sidebarContent}
					/>
				</div>
				<LayoutWellSidebar>{sidebarContent}</LayoutWellSidebar>
			</div>
		</div>
	);
};
