import { useMemo } from "react";
import type { Artifact } from "@/api/artifacts";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { ArtifactCard } from "./artifact-card";
import { ArtifactsFilterComponent } from "./artifacts-filter";
import { ArtifactsHeader } from "./artifacts-header";
import { ArtifactsEmptyState } from "./empty-state";
import type { filterType } from "./types";

export type ArtifactsPageProps = {
	filters: filterType[];
	onFilterChange: (newFilters: filterType[]) => void;
	artifactsCount: number;
	artifactsList: Artifact[];
};

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

	const artifactsListFiltered = useMemo(
		() =>
			// reduced vs set to preserve sort order
			artifactsList.reduce((acc, artifact) => {
				if (!acc.find((a) => a.key === artifact.key)) {
					acc.push(artifact);
				}
				return acc;
			}, [] as Artifact[]),
		[artifactsList],
	);

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

			{artifactsListFiltered.length === 0 ? (
				<ArtifactsEmptyState />
			) : (
				<div className={gridClass}>
					{artifactsListFiltered.map((artifact) => (
						<ArtifactCard key={artifact.id} artifact={artifact} />
					))}
				</div>
			)}
		</div>
	);
};
