export const TASK_RUN_SORT_FILTERS = [
	"EXPECTED_START_TIME_DESC",
	"EXPECTED_START_TIME_ASC",
] as const;
export type TaskRunSortFilters = (typeof TASK_RUN_SORT_FILTERS)[number];
