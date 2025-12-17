import { useCallback, useMemo } from "react";
import type {
	DateRangePreset,
	DateRangeUrlState,
} from "@/components/flow-runs/flow-runs-list/flow-runs-filters/date-range-url-state";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import { useLocalStorage } from "./use-local-storage";

/**
 * LocalStorage Key Naming Convention
 *
 * Following the Vue UI pattern (prefect-ui-library-custom-default-flow-runs-filter),
 * we use the following keys for the React UI:
 *
 * - `prefect-ui-v2-saved-filters`: Array of saved filter objects
 * - `prefect-ui-v2-default-filter-id`: ID of the filter marked as default (or null)
 *
 * This naming convention:
 * 1. Prefixes with "prefect-ui-v2" to namespace and avoid conflicts
 * 2. Uses kebab-case for consistency with web conventions
 * 3. Clearly describes the stored data
 */
const SAVED_FILTERS_STORAGE_KEY = "prefect-ui-v2-saved-filters";
const DEFAULT_FILTER_ID_STORAGE_KEY = "prefect-ui-v2-default-filter-id";

/**
 * Filter values stored in a SavedFilter.
 *
 * Design decisions:
 * - Uses arrays instead of comma-separated strings for consistency with the Vue UI
 *   implementation and better data structure maintainability
 * - Uses camelCase property names (workPools) while URL parameters use kebab-case (work-pools)
 *   See URL_PARAM_TO_FILTER_KEY_MAP for the transformation mapping
 * - Date range uses the same structure as DateRangeUrlState for compatibility
 *
 * Integration with useRunsFilters:
 * - useRunsFilters uses Set<string> for filter values; convert with Array.from() / new Set()
 * - useRunsFilters uses comma-separated strings in URL params; this uses arrays for storage
 */
export type SavedFilterValues = {
	state?: FlowRunState[];
	flows?: string[];
	deployments?: string[];
	workPools?: string[];
	tags?: string[];
	range?: DateRangePreset;
	start?: string;
	end?: string;
};

/**
 * A saved filter configuration that can be persisted to localStorage.
 *
 * The id field uses a timestamp-based UUID for uniqueness.
 * The isDefault field is computed at runtime based on DEFAULT_FILTER_ID_STORAGE_KEY,
 * not stored in the filter object itself.
 */
export type SavedFilter = {
	id: string;
	name: string;
	filters: SavedFilterValues;
};

/**
 * Input type for creating a new saved filter (id is generated automatically).
 */
export type SavedFilterCreate = {
	name: string;
	filters: SavedFilterValues;
};

/**
 * Mapping between URL parameter names (kebab-case) and SavedFilterValues property names (camelCase).
 *
 * This transformation is needed because:
 * - URL parameters use kebab-case for web conventions (e.g., "work-pools")
 * - TypeScript/JavaScript properties use camelCase (e.g., "workPools")
 *
 * When integrating with useRunsFilters, use this mapping to convert between formats:
 * - URL → SavedFilter: urlParamToFilterKey[urlParam]
 * - SavedFilter → URL: filterKeyToUrlParam[filterKey]
 */
export const URL_PARAM_TO_FILTER_KEY_MAP = {
	state: "state",
	flows: "flows",
	deployments: "deployments",
	"work-pools": "workPools",
	tags: "tags",
	range: "range",
	start: "start",
	end: "end",
} as const;

export const FILTER_KEY_TO_URL_PARAM_MAP = {
	state: "state",
	flows: "flows",
	deployments: "deployments",
	workPools: "work-pools",
	tags: "tags",
	range: "range",
	start: "start",
	end: "end",
} as const;

/**
 * Generates a unique ID for a saved filter using timestamp and random string.
 */
function generateFilterId(): string {
	return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Compares two SavedFilterValues objects for equality.
 *
 * This is used to determine if the current filter state matches a saved filter.
 * Arrays are compared by sorting and checking element equality.
 * Date range fields are compared directly.
 *
 * Based on the Vue UI's isSameFilter pattern from src/utilities/savedFilters.ts
 */
export function areFiltersEqual(
	filterA: SavedFilterValues,
	filterB: SavedFilterValues,
): boolean {
	const sortedArrayEqual = (
		a: string[] | undefined,
		b: string[] | undefined,
	): boolean => {
		if (a === undefined && b === undefined) return true;
		if (a === undefined || b === undefined) return false;
		if (a.length !== b.length) return false;
		const sortedA = [...a].sort();
		const sortedB = [...b].sort();
		return sortedA.every((val, idx) => val === sortedB[idx]);
	};

	return (
		sortedArrayEqual(filterA.state, filterB.state) &&
		sortedArrayEqual(filterA.flows, filterB.flows) &&
		sortedArrayEqual(filterA.deployments, filterB.deployments) &&
		sortedArrayEqual(filterA.workPools, filterB.workPools) &&
		sortedArrayEqual(filterA.tags, filterB.tags) &&
		filterA.range === filterB.range &&
		filterA.start === filterB.start &&
		filterA.end === filterB.end
	);
}

/**
 * Converts SavedFilterValues to DateRangeUrlState for use with existing components.
 */
export function filterValuesToDateRangeUrlState(
	filters: SavedFilterValues,
): DateRangeUrlState {
	return {
		range: filters.range,
		start: filters.start,
		end: filters.end,
	};
}

/**
 * Converts DateRangeUrlState to partial SavedFilterValues.
 */
export function dateRangeUrlStateToFilterValues(
	dateRange: DateRangeUrlState,
): Pick<SavedFilterValues, "range" | "start" | "end"> {
	return {
		range: dateRange.range,
		start: dateRange.start,
		end: dateRange.end,
	};
}

export type UseSavedFiltersReturn = {
	savedFilters: SavedFilter[];
	defaultFilterId: string | null;
	saveFilter: (filter: SavedFilterCreate) => SavedFilter;
	deleteFilter: (filterId: string) => void;
	updateFilter: (filterId: string, updates: Partial<SavedFilterCreate>) => void;
	setDefaultFilter: (filterId: string | null) => void;
	getFilterById: (filterId: string) => SavedFilter | undefined;
	findMatchingFilter: (filters: SavedFilterValues) => SavedFilter | undefined;
	isDefaultFilter: (filterId: string) => boolean;
};

/**
 * Hook for managing saved filters in localStorage.
 *
 * This hook provides CRUD operations for saved filters and manages the default filter setting.
 * It uses the existing useLocalStorage hook for persistence.
 *
 * Usage:
 * ```tsx
 * const {
 *   savedFilters,
 *   defaultFilterId,
 *   saveFilter,
 *   deleteFilter,
 *   setDefaultFilter,
 *   findMatchingFilter,
 * } = useSavedFilters();
 *
 * // Save current filters
 * const newFilter = saveFilter({ name: "My Filter", filters: currentFilters });
 *
 * // Set as default
 * setDefaultFilter(newFilter.id);
 *
 * // Check if current filters match a saved filter
 * const matchingFilter = findMatchingFilter(currentFilters);
 * ```
 *
 * Integration with useRunsFilters:
 * When integrating with the existing useRunsFilters hook, you'll need to:
 * 1. Convert Set<string> to string[] when saving: Array.from(filters.states)
 * 2. Convert string[] to Set<string> when applying: new Set(savedFilter.filters.state)
 * 3. Map URL param names using URL_PARAM_TO_FILTER_KEY_MAP / FILTER_KEY_TO_URL_PARAM_MAP
 */
export function useSavedFilters(): UseSavedFiltersReturn {
	const [savedFilters, setSavedFilters] = useLocalStorage<SavedFilter[]>(
		SAVED_FILTERS_STORAGE_KEY,
		[],
	);

	const [defaultFilterId, setDefaultFilterId] = useLocalStorage<string | null>(
		DEFAULT_FILTER_ID_STORAGE_KEY,
		null,
	);

	const saveFilter = useCallback(
		(filterCreate: SavedFilterCreate): SavedFilter => {
			const newFilter: SavedFilter = {
				id: generateFilterId(),
				name: filterCreate.name,
				filters: filterCreate.filters,
			};
			setSavedFilters((prev) => [...prev, newFilter]);
			return newFilter;
		},
		[setSavedFilters],
	);

	const deleteFilter = useCallback(
		(filterId: string): void => {
			setSavedFilters((prev) => prev.filter((f) => f.id !== filterId));
			setDefaultFilterId((prev) => (prev === filterId ? null : prev));
		},
		[setSavedFilters, setDefaultFilterId],
	);

	const updateFilter = useCallback(
		(filterId: string, updates: Partial<SavedFilterCreate>): void => {
			setSavedFilters((prev) =>
				prev.map((f) =>
					f.id === filterId
						? {
								...f,
								...(updates.name !== undefined && { name: updates.name }),
								...(updates.filters !== undefined && {
									filters: updates.filters,
								}),
							}
						: f,
				),
			);
		},
		[setSavedFilters],
	);

	const setDefaultFilter = useCallback(
		(filterId: string | null): void => {
			setDefaultFilterId(filterId);
		},
		[setDefaultFilterId],
	);

	const getFilterById = useCallback(
		(filterId: string): SavedFilter | undefined => {
			return savedFilters.find((f) => f.id === filterId);
		},
		[savedFilters],
	);

	const findMatchingFilter = useCallback(
		(filters: SavedFilterValues): SavedFilter | undefined => {
			return savedFilters.find((f) => areFiltersEqual(f.filters, filters));
		},
		[savedFilters],
	);

	const isDefaultFilter = useMemo(
		() =>
			(filterId: string): boolean => {
				return defaultFilterId === filterId;
			},
		[defaultFilterId],
	);

	return {
		savedFilters,
		defaultFilterId,
		saveFilter,
		deleteFilter,
		updateFilter,
		setDefaultFilter,
		getFilterById,
		findMatchingFilter,
		isDefaultFilter,
	};
}
