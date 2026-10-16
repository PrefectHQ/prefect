import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { LayoutWellSidebar } from "@/components/ui/layout-well";
import { ArtifactDataView } from "./artifact-data-view";
import { ArtifactDetailHeader } from "./artifact-detail-header";
import { ArtifactDetailTabs } from "./artifact-detail-tabs";
import { MetadataSidebar } from "./metadata-sidebar";

export type ArtifactDetailPageProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailPage = ({ artifact }: ArtifactDetailPageProps) => {
	const artifactContent = useMemo(
		() => <ArtifactDataView artifact={artifact} />,
		[artifact],
	);

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
