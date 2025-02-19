export const SORT_FILTERS = [
	"START_TIME_ASC",
	"START_TIME_DESC",
	"NAME_ASC",
	"NAME_DESC",
] as const;
export type SortFilters = (typeof SORT_FILTERS)[number];
