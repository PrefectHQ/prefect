import { useSuspenseQuery } from "@tanstack/react-query";
import isEqual from "lodash/isEqual";
import { useMemo } from "react";
import {
	buildListSavedSearchesQuery,
	type SavedSearch,
	type SavedSearchFilter,
} from "@/api/saved-searches";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { SavedFiltersMenu } from "./saved-filters-menu";
import {
	CUSTOM_FILTER_NAME,
	getDefaultSavedSearchFilter,
	isSameFilter,
	SYSTEM_SAVED_SEARCHES,
} from "./saved-filters-utils";

export type SavedFiltersFilter = {
	state?: string[];
	flow?: string[];
	tag?: string[];
	deployment?: string[];
	workQueue?: string[];
	workPool?: string[];
	range: {
		type: "span";
		seconds: number;
	};
};

export type SavedFlowRunsSearch = {
	id: string | null;
	name: string;
	filters: SavedFiltersFilter;
	isDefault: boolean;
};

type SavedFiltersProps = {
	filter: SavedFiltersFilter;
	onFilterChange: (filter: SavedFiltersFilter) => void;
};

export function SavedFilters({ filter, onFilterChange }: SavedFiltersProps) {
	const { data: apiSavedSearches } = useSuspenseQuery(
		buildListSavedSearchesQuery(),
	);

	const defaultFilter = getDefaultSavedSearchFilter();

	const savedSearches = useMemo<SavedFlowRunsSearch[]>(() => {
		const systemSearches = SYSTEM_SAVED_SEARCHES.map((search) => ({
			...search,
			isDefault: isSameFilter(search.filters, defaultFilter),
		}));

		const userSearches: SavedFlowRunsSearch[] = apiSavedSearches.map(
			(search: SavedSearch) => ({
				id: search.id,
				name: search.name,
				filters: convertApiFiltersToSavedFiltersFilter(search.filters ?? []),
				isDefault: false,
			}),
		);

		return [...systemSearches, ...userSearches];
	}, [apiSavedSearches, defaultFilter]);

	const selectedSearch = useMemo<SavedFlowRunsSearch | null>(() => {
		const found = savedSearches.find((search) =>
			isSameFilter(search.filters, filter),
		);
		return found ?? null;
	}, [savedSearches, filter]);

	const isCustomFilter = selectedSearch === null;

	const options = useMemo(() => {
		const items = savedSearches.map((search) => ({
			label: search.isDefault ? `${search.name} (default)` : search.name,
			value: search.name,
			disabled: false,
		}));

		if (isCustomFilter) {
			return [
				{
					label: CUSTOM_FILTER_NAME,
					value: CUSTOM_FILTER_NAME,
					disabled: true,
				},
				...items,
			];
		}

		return items;
	}, [savedSearches, isCustomFilter]);

	const handleValueChange = (name: string) => {
		const search = savedSearches.find((s) => s.name === name);
		if (search) {
			onFilterChange(search.filters);
		}
	};

	const currentValue = selectedSearch?.name ?? CUSTOM_FILTER_NAME;

	const currentSearch: SavedFlowRunsSearch = selectedSearch ?? {
		id: null,
		name: CUSTOM_FILTER_NAME,
		filters: filter,
		isDefault: false,
	};

	return (
		<div className="flex items-center gap-2">
			<Select value={currentValue} onValueChange={handleValueChange}>
				<SelectTrigger className="w-[180px]">
					<SelectValue placeholder="Select a filter" />
				</SelectTrigger>
				<SelectContent>
					{options.map((option) => (
						<SelectItem
							key={option.value}
							value={option.value}
							disabled={option.disabled}
						>
							{option.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
			<SavedFiltersMenu
				savedSearch={currentSearch}
				onSaved={(savedSearch) => {
					onFilterChange(savedSearch.filters);
				}}
				onDeleted={() => {
					const defaultSearch = savedSearches.find((s) => s.isDefault);
					if (defaultSearch) {
						onFilterChange(defaultSearch.filters);
					}
				}}
			/>
		</div>
	);
}

function convertApiFiltersToSavedFiltersFilter(
	apiFilters: SavedSearchFilter[],
): SavedFiltersFilter {
	const result: SavedFiltersFilter = {
		state: [],
		flow: [],
		tag: [],
		deployment: [],
		workQueue: [],
		workPool: [],
		range: { type: "span", seconds: -604800 },
	};

	for (const filter of apiFilters) {
		if (filter.object === "flow_run" && filter.property === "state") {
			if (Array.isArray(filter.value)) {
				result.state = filter.value as string[];
			}
		} else if (filter.object === "flow" && filter.property === "id") {
			if (Array.isArray(filter.value)) {
				result.flow = filter.value as string[];
			}
		} else if (filter.object === "flow_run" && filter.property === "tags") {
			if (Array.isArray(filter.value)) {
				result.tag = filter.value as string[];
			}
		} else if (filter.object === "deployment" && filter.property === "id") {
			if (Array.isArray(filter.value)) {
				result.deployment = filter.value as string[];
			}
		} else if (filter.object === "work_queue" && filter.property === "id") {
			if (Array.isArray(filter.value)) {
				result.workQueue = filter.value as string[];
			}
		} else if (filter.object === "work_pool" && filter.property === "id") {
			if (Array.isArray(filter.value)) {
				result.workPool = filter.value as string[];
			}
		} else if (filter.object === "flow_run" && filter.property === "range") {
			if (
				typeof filter.value === "object" &&
				filter.value !== null &&
				"seconds" in filter.value
			) {
				result.range = filter.value as { type: "span"; seconds: number };
			}
		}
	}

	return result;
}

export function convertSavedFiltersFilterToApiFilters(
	filter: SavedFiltersFilter,
): SavedSearchFilter[] {
	const apiFilters: SavedSearchFilter[] = [];

	if (filter.state && filter.state.length > 0) {
		apiFilters.push({
			object: "flow_run",
			property: "state",
			type: "string",
			operation: "any",
			value: filter.state,
		});
	}

	if (filter.flow && filter.flow.length > 0) {
		apiFilters.push({
			object: "flow",
			property: "id",
			type: "string",
			operation: "any",
			value: filter.flow,
		});
	}

	if (filter.tag && filter.tag.length > 0) {
		apiFilters.push({
			object: "flow_run",
			property: "tags",
			type: "string",
			operation: "any",
			value: filter.tag,
		});
	}

	if (filter.deployment && filter.deployment.length > 0) {
		apiFilters.push({
			object: "deployment",
			property: "id",
			type: "string",
			operation: "any",
			value: filter.deployment,
		});
	}

	if (filter.workQueue && filter.workQueue.length > 0) {
		apiFilters.push({
			object: "work_queue",
			property: "id",
			type: "string",
			operation: "any",
			value: filter.workQueue,
		});
	}

	if (filter.workPool && filter.workPool.length > 0) {
		apiFilters.push({
			object: "work_pool",
			property: "id",
			type: "string",
			operation: "any",
			value: filter.workPool,
		});
	}

	apiFilters.push({
		object: "flow_run",
		property: "range",
		type: "object",
		operation: "equals",
		value: filter.range,
	});

	return apiFilters;
}

export { isEqual };
