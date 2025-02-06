import { Artifact } from "@/api/artifacts";
import { ArtifactCard } from "./artifact-card";
import { ArtifactsFilterComponent } from "./artifacts-filter";
import { ArtifactsHeader } from "./artifacts-header";
import { filterType } from "./types";

interface ArtifactsPageProps {
	filters: filterType[];
	onFilterChange: (newFilters: filterType[]) => void;
	artifactsCount: number;
	artifactsList: Artifact[];
}

export const ArtifactsPage = ({
	filters,
	onFilterChange,
	artifactsList,
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
			<div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
				{artifactsList.map((artifact) => (
					<ArtifactCard key={artifact.id} artifact={artifact} />
				))}
			</div>
		</div>
	);
};
