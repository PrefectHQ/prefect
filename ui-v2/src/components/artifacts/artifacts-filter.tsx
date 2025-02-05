import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import useDebounce from "@/hooks/use-debounce";
import { useCallback, useEffect, useMemo, useState } from "react";
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
];

export const ArtifactsFilterComponent = ({
	filters,
	onFilterChange,
	totalCount,
}: ArtifactsFilterProps) => {
	const [searchInputValue, setSearchInput] = useState(
		filters.find((val) => val.id == "name")?.value ?? "",
	);

	const debouncedSearchInputValue = useDebounce(searchInputValue, 500);

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

	useEffect(() => {
		changeArtifactName(debouncedSearchInputValue);
	}, [debouncedSearchInputValue, changeArtifactName]);

	const typeValue = useMemo(
		() => filters.find((val) => val.id == "type")?.value ?? undefined,
		[filters],
	);
	return (
		<div className="flex justify-between items-center mt-4">
			<div>
				{/* <p>{totalCount} artifacts </p> */}
				<Typography variant="body" className="text-sm text-muted-foreground">
					{totalCount} artifacts
				</Typography>
			</div>
			<div className="flex gap-4">
				<SearchInput
					value={searchInputValue}
					onChange={(e) => setSearchInput(e.target.value)}
				/>

				<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
					<Select
						value={typeValue}
						onValueChange={changeArtifactType}
						defaultValue="undefined"
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
