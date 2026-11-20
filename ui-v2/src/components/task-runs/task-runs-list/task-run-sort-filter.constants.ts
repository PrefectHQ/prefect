export const TASK_RUN_SORT_FILTERS = [
	"EXPECTED_START_TIME_DESC",
	"EXPECTED_START_TIME_ASC",
	"DURATION_DESC",
	"DURATION_ASC",
] as const;
export type TaskRunSortFilters = (typeof TASK_RUN_SORT_FILTERS)[number];
