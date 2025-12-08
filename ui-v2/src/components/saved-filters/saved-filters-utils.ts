import isEqual from "lodash/isEqual";
import type { SavedFiltersFilter, SavedFlowRunsSearch } from "./saved-filters";

const SECONDS_IN_WEEK = 7 * 24 * 60 * 60;

export const CUSTOM_FILTER_NAME = "Custom";
export const UNSAVED_FILTER_NAME = "Unsaved";

export const FILTER_RANGE_PAST_WEEK = {
	type: "span" as const,
	seconds: -SECONDS_IN_WEEK,
};

export const ONE_WEEK_FILTER: SavedFiltersFilter = {
	range: FILTER_RANGE_PAST_WEEK,
	state: [],
	flow: [],
	tag: [],
	deployment: [],
	workPool: [],
	workQueue: [],
};

export const PREFECT_STATE_NAMES_WITHOUT_SCHEDULED = [
	"Completed",
	"Failed",
	"Cancelled",
	"Cancelling",
	"Running",
	"Pending",
	"Crashed",
	"Paused",
	"Retrying",
	"AwaitingRetry",
	"Late",
];

export const NO_SCHEDULE_FILTER: SavedFiltersFilter = {
	range: FILTER_RANGE_PAST_WEEK,
	state: [...PREFECT_STATE_NAMES_WITHOUT_SCHEDULED],
	flow: [],
	tag: [],
	deployment: [],
	workPool: [],
	workQueue: [],
};

export const ONE_WEEK_SAVED_SEARCH: Omit<SavedFlowRunsSearch, "isDefault"> = {
	id: null,
	name: "Past week",
	filters: ONE_WEEK_FILTER,
};

export const EXCLUDE_SCHEDULED_SAVED_SEARCH: Omit<
	SavedFlowRunsSearch,
	"isDefault"
> = {
	id: null,
	name: "Hide scheduled runs",
	filters: NO_SCHEDULE_FILTER,
};

export const SYSTEM_SAVED_SEARCHES: Omit<SavedFlowRunsSearch, "isDefault">[] = [
	ONE_WEEK_SAVED_SEARCH,
	EXCLUDE_SCHEDULED_SAVED_SEARCH,
];

export const SYSTEM_DEFAULT_SAVED_SEARCH = ONE_WEEK_SAVED_SEARCH;

const LOCAL_STORAGE_KEY = "prefect-ui-custom-default-flow-runs-filter";

export function isSameFilter(
	filterA: SavedFiltersFilter,
	filterB: SavedFiltersFilter,
): boolean {
	return isEqual(filterA, filterB);
}

export function getDefaultSavedSearchFilter(): SavedFiltersFilter {
	try {
		const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
		if (stored) {
			return JSON.parse(stored) as SavedFiltersFilter;
		}
	} catch {
		// Ignore parse errors
	}
	return SYSTEM_DEFAULT_SAVED_SEARCH.filters;
}

export function setDefaultSavedSearchFilter(filter: SavedFiltersFilter): void {
	if (isSameFilter(filter, SYSTEM_DEFAULT_SAVED_SEARCH.filters)) {
		localStorage.removeItem(LOCAL_STORAGE_KEY);
	} else {
		localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(filter));
	}
}

export function removeDefaultSavedSearchFilter(): void {
	localStorage.removeItem(LOCAL_STORAGE_KEY);
}

export function isCustomDefaultFilter(): boolean {
	return localStorage.getItem(LOCAL_STORAGE_KEY) !== null;
}
