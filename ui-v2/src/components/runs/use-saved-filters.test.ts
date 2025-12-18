/* eslint-disable @typescript-eslint/unbound-method */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	areFiltersEqual,
	dateRangeUrlStateToFilterValues,
	FILTER_KEY_TO_URL_PARAM_MAP,
	filterValuesToDateRangeUrlState,
	type SavedFilter,
	type SavedFilterValues,
	SYSTEM_FILTERS,
	URL_PARAM_TO_FILTER_KEY_MAP,
	useSavedFilters,
} from "./use-saved-filters";

describe("areFiltersEqual", () => {
	it("returns true for identical empty filters", () => {
		const filterA: SavedFilterValues = {};
		const filterB: SavedFilterValues = {};
		expect(areFiltersEqual(filterA, filterB)).toBe(true);
	});

	it("returns true for filters with same arrays in different order", () => {
		const filterA: SavedFilterValues = {
			state: ["Completed", "Failed"],
			flows: ["flow-1", "flow-2"],
		};
		const filterB: SavedFilterValues = {
			state: ["Failed", "Completed"],
			flows: ["flow-2", "flow-1"],
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(true);
	});

	it("returns false for filters with different arrays", () => {
		const filterA: SavedFilterValues = {
			state: ["Completed"],
		};
		const filterB: SavedFilterValues = {
			state: ["Failed"],
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(false);
	});

	it("returns false when one filter has undefined and other has empty array", () => {
		const filterA: SavedFilterValues = {
			state: undefined,
		};
		const filterB: SavedFilterValues = {
			state: [],
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(false);
	});

	it("returns true for filters with same date range", () => {
		const filterA: SavedFilterValues = {
			range: "past-7-days",
		};
		const filterB: SavedFilterValues = {
			range: "past-7-days",
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(true);
	});

	it("returns false for filters with different date ranges", () => {
		const filterA: SavedFilterValues = {
			range: "past-7-days",
		};
		const filterB: SavedFilterValues = {
			range: "past-24-hours",
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(false);
	});

	it("returns true for filters with same custom date range", () => {
		const filterA: SavedFilterValues = {
			start: "2024-01-01T00:00:00.000Z",
			end: "2024-01-31T23:59:59.999Z",
		};
		const filterB: SavedFilterValues = {
			start: "2024-01-01T00:00:00.000Z",
			end: "2024-01-31T23:59:59.999Z",
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(true);
	});

	it("returns true for complex filters with all fields matching", () => {
		const filterA: SavedFilterValues = {
			state: ["Completed", "Failed"],
			flows: ["flow-1"],
			deployments: ["deploy-1", "deploy-2"],
			workPools: ["pool-1"],
			tags: ["tag-a", "tag-b"],
			range: "past-7-days",
		};
		const filterB: SavedFilterValues = {
			state: ["Failed", "Completed"],
			flows: ["flow-1"],
			deployments: ["deploy-2", "deploy-1"],
			workPools: ["pool-1"],
			tags: ["tag-b", "tag-a"],
			range: "past-7-days",
		};
		expect(areFiltersEqual(filterA, filterB)).toBe(true);
	});
});

describe("filterValuesToDateRangeUrlState", () => {
	it("extracts date range fields from filter values", () => {
		const filters: SavedFilterValues = {
			state: ["Completed"],
			range: "past-7-days",
			start: undefined,
			end: undefined,
		};
		expect(filterValuesToDateRangeUrlState(filters)).toEqual({
			range: "past-7-days",
			start: undefined,
			end: undefined,
		});
	});

	it("extracts custom date range", () => {
		const filters: SavedFilterValues = {
			start: "2024-01-01T00:00:00.000Z",
			end: "2024-01-31T23:59:59.999Z",
		};
		expect(filterValuesToDateRangeUrlState(filters)).toEqual({
			range: undefined,
			start: "2024-01-01T00:00:00.000Z",
			end: "2024-01-31T23:59:59.999Z",
		});
	});
});

describe("dateRangeUrlStateToFilterValues", () => {
	it("converts date range url state to filter values", () => {
		const dateRange = {
			range: "past-7-days" as const,
			start: undefined,
			end: undefined,
		};
		expect(dateRangeUrlStateToFilterValues(dateRange)).toEqual({
			range: "past-7-days",
			start: undefined,
			end: undefined,
		});
	});
});

describe("URL_PARAM_TO_FILTER_KEY_MAP", () => {
	it("maps work-pools to workPools", () => {
		expect(URL_PARAM_TO_FILTER_KEY_MAP["work-pools"]).toBe("workPools");
	});

	it("maps other params directly", () => {
		expect(URL_PARAM_TO_FILTER_KEY_MAP.state).toBe("state");
		expect(URL_PARAM_TO_FILTER_KEY_MAP.flows).toBe("flows");
		expect(URL_PARAM_TO_FILTER_KEY_MAP.deployments).toBe("deployments");
		expect(URL_PARAM_TO_FILTER_KEY_MAP.tags).toBe("tags");
	});
});

describe("FILTER_KEY_TO_URL_PARAM_MAP", () => {
	it("maps workPools to work-pools", () => {
		expect(FILTER_KEY_TO_URL_PARAM_MAP.workPools).toBe("work-pools");
	});

	it("maps other keys directly", () => {
		expect(FILTER_KEY_TO_URL_PARAM_MAP.state).toBe("state");
		expect(FILTER_KEY_TO_URL_PARAM_MAP.flows).toBe("flows");
		expect(FILTER_KEY_TO_URL_PARAM_MAP.deployments).toBe("deployments");
		expect(FILTER_KEY_TO_URL_PARAM_MAP.tags).toBe("tags");
	});
});

describe("useSavedFilters", () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
	});

	it("initializes with system filters only", () => {
		const { result } = renderHook(() => useSavedFilters());
		// savedFilters includes system filters by default
		expect(result.current.savedFilters).toEqual(SYSTEM_FILTERS);
		expect(result.current.defaultFilterId).toBeNull();
	});

	it("saves a new filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter | undefined;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		// savedFilters includes system filters + user-saved filters
		expect(result.current.savedFilters).toHaveLength(SYSTEM_FILTERS.length + 1);
		// User-saved filters come after system filters
		const userFilter = result.current.savedFilters[SYSTEM_FILTERS.length];
		expect(userFilter.name).toBe("My Filter");
		expect(userFilter.filters.state).toEqual(["Completed"]);
		expect(savedFilter).toBeDefined();
		expect(userFilter.id).toBe(savedFilter?.id);
	});

	it("deletes a filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		// savedFilters includes system filters + user-saved filters
		expect(result.current.savedFilters).toHaveLength(SYSTEM_FILTERS.length + 1);

		act(() => {
			result.current.deleteFilter(savedFilter.id);
		});

		// After deletion, only system filters remain
		expect(result.current.savedFilters).toHaveLength(SYSTEM_FILTERS.length);
	});

	it("updates a filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		act(() => {
			result.current.updateFilter(savedFilter.id, {
				name: "Updated Filter",
				filters: { state: ["Failed"] },
			});
		});

		// User-saved filters come after system filters
		const userFilter = result.current.savedFilters[SYSTEM_FILTERS.length];
		expect(userFilter.name).toBe("Updated Filter");
		expect(userFilter.filters.state).toEqual(["Failed"]);
	});

	it("sets and clears default filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter | undefined;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		if (!savedFilter) {
			throw new Error("Expected savedFilter to be created");
		}

		const filterId = savedFilter.id;

		act(() => {
			result.current.setDefaultFilter(filterId);
		});

		expect(result.current.defaultFilterId).toBe(filterId);
		expect(result.current.isDefaultFilter(filterId)).toBe(true);

		act(() => {
			result.current.setDefaultFilter(null);
		});

		expect(result.current.defaultFilterId).toBeNull();
		expect(result.current.isDefaultFilter(filterId)).toBe(false);
	});

	it("clears default filter when deleting the default filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter | undefined;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
			if (!savedFilter) {
				throw new Error("Expected savedFilter to be created");
			}
			result.current.setDefaultFilter(savedFilter.id);
		});

		if (!savedFilter) {
			throw new Error("Expected savedFilter to be created");
		}

		const filterId = savedFilter.id;

		expect(result.current.defaultFilterId).toBe(filterId);

		act(() => {
			result.current.deleteFilter(filterId);
		});

		expect(result.current.defaultFilterId).toBeNull();
	});

	it("gets filter by id", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter | undefined;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		if (!savedFilter) {
			throw new Error("Expected savedFilter to be created");
		}

		const found = result.current.getFilterById(savedFilter.id);
		expect(found).toBeDefined();
		expect(found?.name).toBe("My Filter");

		const notFound = result.current.getFilterById("non-existent-id");
		expect(notFound).toBeUndefined();
	});

	it("finds matching filter", () => {
		const { result } = renderHook(() => useSavedFilters());

		act(() => {
			result.current.saveFilter({
				name: "Completed Filter",
				filters: { state: ["Completed"] },
			});
			result.current.saveFilter({
				name: "Failed Filter",
				filters: { state: ["Failed"] },
			});
		});

		const matchingFilter = result.current.findMatchingFilter({
			state: ["Completed"],
		});
		expect(matchingFilter).toBeDefined();
		expect(matchingFilter?.name).toBe("Completed Filter");

		const noMatch = result.current.findMatchingFilter({
			state: ["Running"],
		});
		expect(noMatch).toBeUndefined();
	});

	it("persists filters to localStorage", () => {
		const { result } = renderHook(() => useSavedFilters());

		act(() => {
			result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
		});

		expect(localStorage.setItem).toHaveBeenCalledWith(
			"prefect-ui-v2-saved-filters",
			expect.stringContaining("My Filter"),
		);
	});

	it("persists default filter id to localStorage", () => {
		const { result } = renderHook(() => useSavedFilters());

		let savedFilter: SavedFilter | undefined;
		act(() => {
			savedFilter = result.current.saveFilter({
				name: "My Filter",
				filters: { state: ["Completed"] },
			});
			if (savedFilter) {
				result.current.setDefaultFilter(savedFilter.id);
			}
		});

		expect(savedFilter).toBeDefined();
		expect(localStorage.setItem).toHaveBeenCalledWith(
			"prefect-ui-v2-default-filter-id",
			expect.stringContaining(savedFilter?.id ?? ""),
		);
	});
});
