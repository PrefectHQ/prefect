import { Artifact } from "@/api/artifacts";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { useMemo } from "react";
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
	const [displayMode, setDisplayMode] = useLocalStorage<string>(
		"artifacts-grid-style",
		"grid",
	);

	const gridClass = useMemo(() => {
		return displayMode === "grid"
			? "grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4"
			: "grid-cols-1";
	}, [displayMode]);
	return (
		<div className="flex flex-col gap-4">
			<ArtifactsHeader />
			<ArtifactsFilterComponent
				filters={filters}
				onFilterChange={onFilterChange}
				totalCount={artifactsCount}
				setDisplayMode={setDisplayMode}
				displayMode={displayMode}
			/>

			<div className={gridClass}>
				{artifactsList.map((artifact) => (
					<ArtifactCard key={artifact.id} artifact={artifact} />
				))}
			</div>
		</div>
	);
};
