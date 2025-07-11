import { useCallback, useMemo } from "react";
import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { pluralize } from "@/utils";
import { Icon } from "../ui/icons";
import { ToggleGroup, ToggleGroupItem } from "../ui/toggle-group";
import { Typography } from "../ui/typography";
import type { filterType } from "./types";

type ArtifactsFilterProps = {
	filters: filterType[];
	onFilterChange: (newFilters: filterType[]) => void;
	totalCount: number;
	setDisplayMode: (mode: string) => void;
	displayMode: string;
};

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
	displayMode,
	setDisplayMode,
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
		() => filters.find((val) => val.id === "type")?.value,
		[filters],
	);

	const nameValue = useMemo(
		() => filters.find((val) => val.id === "name")?.value,
		[filters],
	);
	return (
		<div
			data-testid="artifact-filter"
			className="flex justify-between items-center"
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

				<div className="flex gap-4">
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
					<div>
						<ToggleGroup
							type="single"
							defaultValue={displayMode}
							onValueChange={(value: string) => setDisplayMode(value)}
						>
							<ToggleGroupItem data-testid="grid-layout" value="grid">
								<Icon id="LayoutGrid" />
							</ToggleGroupItem>
							<ToggleGroupItem data-testid="list-layout" value="list">
								<Icon id="AlignJustify" />
							</ToggleGroupItem>
						</ToggleGroup>
					</div>
				</div>
			</div>
		</div>
	);
};
