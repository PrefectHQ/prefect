import { Artifact } from "@/api/artifacts";
import { ArtifactsFilterComponent } from "./artifacts-filter";
import { ArtifactsHeader } from "./artifacts-header";
import { filterType } from "./types";
// import { ArtifactCard } from "./artifact-card";

interface ArtifactsPageProps {
	filters: filterType[];
	onFilterChange: (newFilters: filterType[]) => void;
	artifactsCount: number;
	artifactsList: Artifact[];
}

export const ArtifactsPage = ({
	filters,
	onFilterChange,
	// artifactsList,
	artifactsCount,
}: ArtifactsPageProps) => {
	return (
		<div>
			<ArtifactsHeader />
			<ArtifactsFilterComponent
				filters={filters}
				onFilterChange={onFilterChange}
				totalCount={artifactsCount}
			/>
			{/* <div className="flex flex-wrap">
            {
                artifactsList.map((artifact) => (
                    <ArtifactCard key={artifact.id} artifact={artifact} />
                ))
            }
            </div> */}
		</div>
	);
};
