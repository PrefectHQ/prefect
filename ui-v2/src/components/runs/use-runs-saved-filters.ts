import { getRouteApi } from "@tanstack/react-router";
import { useCallback, useMemo, useState } from "react";
import type { SavedFilter as SavedFiltersMenuFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/saved-filters-menu";
import {
	type SavedFilter,
	type SavedFilterValues,
	useSavedFilters,
} from "./use-saved-filters";

const routeApi = getRouteApi("/runs/");

/**
 * Converts URL search params to SavedFilterValues format.
 * URL params use comma-separated strings, SavedFilterValues uses arrays.
 */
function urlParamsToFilterValues(search: {
	state?: string;
	flows?: string;
	deployments?: string;
	"work-pools"?: string;
	tags?: string;
	range?: string;
	start?: string;
	end?: string;
}): SavedFilterValues {
	const parseCommaSeparated = (value: string | undefined): string[] => {
		if (!value) return [];
		return value.split(",").filter((s) => s.trim().length > 0);
	};

	const stateArray = parseCommaSeparated(search.state);
	const flowsArray = parseCommaSeparated(search.flows);
	const deploymentsArray = parseCommaSeparated(search.deployments);
	const workPoolsArray = parseCommaSeparated(search["work-pools"]);
	const tagsArray = parseCommaSeparated(search.tags);

	return {
		...(stateArray.length > 0 && {
			state: stateArray as SavedFilterValues["state"],
		}),
		...(flowsArray.length > 0 && { flows: flowsArray }),
		...(deploymentsArray.length > 0 && { deployments: deploymentsArray }),
		...(workPoolsArray.length > 0 && { workPools: workPoolsArray }),
		...(tagsArray.length > 0 && { tags: tagsArray }),
		...(search.range && { range: search.range as SavedFilterValues["range"] }),
		...(search.start && { start: search.start }),
		...(search.end && { end: search.end }),
	};
}

/**
 * Converts SavedFilterValues to URL search params format.
 * SavedFilterValues uses arrays, URL params use comma-separated strings.
 */
function filterValuesToUrlParams(filters: SavedFilterValues): {
	state: string;
	flows: string;
	deployments: string;
	"work-pools": string;
	tags: string;
	range: string | undefined;
	start: string | undefined;
	end: string | undefined;
} {
	return {
		state: filters.state?.join(",") ?? "",
		flows: filters.flows?.join(",") ?? "",
		deployments: filters.deployments?.join(",") ?? "",
		"work-pools": filters.workPools?.join(",") ?? "",
		tags: filters.tags?.join(",") ?? "",
		range: filters.range,
		start: filters.start,
		end: filters.end,
	};
}

/**
 * Converts a SavedFilter from the hook to the format expected by SavedFiltersMenu.
 */
function toMenuFilter(
	filter: SavedFilter,
	defaultFilterId: string | null,
): SavedFiltersMenuFilter {
	return {
		id: filter.id,
		name: filter.name,
		isDefault: filter.id === defaultFilterId,
	};
}

export type UseRunsSavedFiltersReturn = {
	/** The currently active filter (matches current URL state), or null if custom/unsaved */
	currentFilter: SavedFiltersMenuFilter | null;
	/** All saved filters formatted for the menu */
	savedFiltersForMenu: SavedFiltersMenuFilter[];
	/** Handler for selecting a filter from the menu */
	onSelectFilter: (filter: SavedFiltersMenuFilter) => void;
	/** Handler for saving the current filter state */
	onSaveFilter: () => void;
	/** Handler for deleting a filter */
	onDeleteFilter: (id: string) => void;
	/** Handler for setting a filter as default */
	onSetDefault: (id: string) => void;
	/** Handler for removing a filter as default */
	onRemoveDefault: (id: string) => void;
	/** Whether the save dialog is open */
	isSaveDialogOpen: boolean;
	/** Handler to close the save dialog */
	closeSaveDialog: () => void;
	/** Handler to confirm saving with a name */
	confirmSave: (name: string) => void;
};

/**
 * Hook that integrates useSavedFilters with the runs page URL state.
 *
 * This hook:
 * 1. Reads current filter state from URL params
 * 2. Finds matching saved filter (if any)
 * 3. Provides handlers for the SavedFiltersMenu component
 * 4. Manages the save dialog state
 */
export function useRunsSavedFilters(): UseRunsSavedFiltersReturn {
	const search = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const {
		savedFilters,
		defaultFilterId,
		saveFilter,
		deleteFilter,
		setDefaultFilter,
		findMatchingFilter,
	} = useSavedFilters();

	const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);

	// Convert current URL state to filter values
	const currentFilterValues = useMemo(
		() => urlParamsToFilterValues(search),
		[search],
	);

	// Find if current URL state matches any saved filter
	const matchingSavedFilter = useMemo(
		() => findMatchingFilter(currentFilterValues),
		[findMatchingFilter, currentFilterValues],
	);

	// Convert saved filters to menu format
	const savedFiltersForMenu = useMemo(
		() => savedFilters.map((f) => toMenuFilter(f, defaultFilterId)),
		[savedFilters, defaultFilterId],
	);

	// Current filter for the menu (null if custom/unsaved)
	const currentFilter = useMemo((): SavedFiltersMenuFilter | null => {
		if (matchingSavedFilter) {
			return toMenuFilter(matchingSavedFilter, defaultFilterId);
		}
		// Check if there are any active filters
		const hasActiveFilters =
			currentFilterValues.state?.length ||
			currentFilterValues.flows?.length ||
			currentFilterValues.deployments?.length ||
			currentFilterValues.workPools?.length ||
			currentFilterValues.tags?.length ||
			currentFilterValues.range ||
			currentFilterValues.start ||
			currentFilterValues.end;

		if (hasActiveFilters) {
			// Return "Unsaved" filter indicator
			return {
				id: null,
				name: "Unsaved",
				isDefault: false,
			};
		}

		// No filters active - return "Custom" (default state)
		return {
			id: null,
			name: "Custom",
			isDefault: false,
		};
	}, [matchingSavedFilter, defaultFilterId, currentFilterValues]);

	// Handler for selecting a filter from the menu
	const onSelectFilter = useCallback(
		(filter: SavedFiltersMenuFilter) => {
			// Find the full saved filter to get the filter values
			const savedFilter = savedFilters.find((f) => f.id === filter.id);
			if (!savedFilter) return;

			const urlParams = filterValuesToUrlParams(savedFilter.filters);

			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					...urlParams,
					page: 1, // Reset pagination when applying filter
				}),
				replace: true,
			});
		},
		[navigate, savedFilters],
	);

	// Handler for initiating save (opens dialog)
	const onSaveFilter = useCallback(() => {
		setIsSaveDialogOpen(true);
	}, []);

	// Handler for confirming save with a name
	const confirmSave = useCallback(
		(name: string) => {
			saveFilter({
				name,
				filters: currentFilterValues,
			});
			setIsSaveDialogOpen(false);
		},
		[saveFilter, currentFilterValues],
	);

	// Handler for closing the save dialog
	const closeSaveDialog = useCallback(() => {
		setIsSaveDialogOpen(false);
	}, []);

	// Handler for deleting a filter
	const onDeleteFilter = useCallback(
		(id: string) => {
			deleteFilter(id);
		},
		[deleteFilter],
	);

	// Handler for setting a filter as default
	const onSetDefault = useCallback(
		(id: string) => {
			setDefaultFilter(id);
		},
		[setDefaultFilter],
	);

	// Handler for removing a filter as default
	const onRemoveDefault = useCallback(() => {
		setDefaultFilter(null);
	}, [setDefaultFilter]);

	return {
		currentFilter,
		savedFiltersForMenu,
		onSelectFilter,
		onSaveFilter,
		onDeleteFilter,
		onSetDefault,
		onRemoveDefault,
		isSaveDialogOpen,
		closeSaveDialog,
		confirmSave,
	};
}

/**
 * Hook to apply the default filter on initial page load.
 * Should be called in the route component.
 */
export function useApplyDefaultFilterOnMount(): void {
	const navigate = routeApi.useNavigate();
	const search = routeApi.useSearch();
	const { savedFilters, defaultFilterId, getFilterById } = useSavedFilters();

	// Check if we should apply default filter on mount
	useMemo(() => {
		// Only apply if:
		// 1. There's a default filter set
		// 2. No filters are currently active in URL
		// 3. We have saved filters loaded
		if (!defaultFilterId || savedFilters.length === 0) return;

		const hasActiveFilters =
			search.state ||
			search.flows ||
			search.deployments ||
			search["work-pools"] ||
			search.tags ||
			search.range ||
			search.start ||
			search.end;

		if (hasActiveFilters) return;

		const defaultFilter = getFilterById(defaultFilterId);
		if (!defaultFilter) return;

		const urlParams = filterValuesToUrlParams(defaultFilter.filters);

		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				...urlParams,
			}),
			replace: true,
		});
	}, [defaultFilterId, savedFilters.length, search, getFilterById, navigate]);
}
