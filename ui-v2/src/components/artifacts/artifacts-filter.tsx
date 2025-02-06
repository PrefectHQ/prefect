import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { pluralize } from "@/utils";
import { useCallback, useMemo } from "react";
import { Typography } from "../ui/typography";
import { filterType } from "./types";

interface ArtifactsFilterProps {
	filters: filterType[];
	onFilterChange: (newFilters: filterType[]) => void;
	totalCount: number;
}

const artifactTypeOptions = [
	{ value: "all", label: "All Types" },
	{ value: "markdown", label: "Markdown" },
	{ value: "progress", label: "Progress" },
	{ value: "image", label: "Image" },
	{ value: "table", label: "Table" },
] as const;

export const ArtifactsFilterComponent = ({
	filters,
	onFilterChange,
	totalCount,
}: ArtifactsFilterProps) => {
	const changeArtifactName = useCallback(
		(value: string) => {
			onFilterChange([
				...filters.filter((filter) => filter.id !== "name"),
				{ id: "name", label: "Name", value },
			]);
		},
		[filters, onFilterChange],
	);

	const changeArtifactType = useCallback(
		(value: string) => {
			onFilterChange([
				...filters.filter((filter) => filter.id !== "type"),
				{ id: "type", label: "Type", value },
			]);
		},
		[filters, onFilterChange],
	);

	const typeValue = useMemo(
		() => filters.find((val) => val.id == "type")?.value,
		[filters],
	);

	const nameValue = useMemo(
		() => filters.find((val) => val.id == "name")?.value,
		[filters],
	);
	return (
		<div
			data-testid="artifact-filter"
			className="flex justify-between items-center mt-4"
		>
			<div>
				<Typography variant="body" className="text-sm text-muted-foreground">
					{totalCount} {pluralize(totalCount, "artifact")}
				</Typography>
			</div>
			<div className="flex gap-4">
				<SearchInput
					data-testid="search-input"
					defaultValue={nameValue}
					placeholder="Search artifacts"
					onChange={(e) => changeArtifactName(e.target.value)}
				/>

				<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
					<Select
						data-testid="type-select"
						value={typeValue}
						onValueChange={changeArtifactType}
					>
						<SelectTrigger aria-label="Artifact type">
							<SelectValue placeholder="Type" />
						</SelectTrigger>
						<SelectContent>
							{artifactTypeOptions.map(({ value, label }) => (
								<SelectItem key={value} value={value}>
									{label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			</div>
		</div>
	);
};
