import type { FlowRunsCountFilter, FlowRunsFilter } from "@/api/flow-runs";
import type {
	TaskRunsCountFilter,
	TaskRunsHistoryFilter,
} from "@/api/task-runs";

/**
 * Builds the filter for fetching flow runs for the history card.
 * Uses a stable date range (7 days ago to now) computed inside queryFn
 * to avoid query key instability with Suspense.
 */
export function buildFlowRunsHistoryFilter(
	flowId: string,
	limit: number,
): FlowRunsFilter {
	return {
		flows: { operator: "and_", id: { any_: [flowId] } },
		flow_runs: {
			operator: "and_",
			start_time: { is_null_: false },
		},
		offset: 0,
		limit,
		sort: "START_TIME_DESC",
	};
}

/**
 * Builds the filter for counting flow runs in the past 7 days.
 */
export function buildFlowRunsCountFilterForHistory(
	flowId: string,
): FlowRunsCountFilter {
	return {
		flows: { operator: "and_", id: { any_: [flowId] } },
		flow_runs: {
			operator: "and_",
			start_time: { is_null_: false },
		},
	};
}

/**
 * Builds the base filter for task run count queries for a specific flow.
 * This filters task runs by flows that match the given flow ID.
 */
function buildBaseCountFilter(flowId: string): {
	task_runs: NonNullable<TaskRunsCountFilter["task_runs"]>;
	flows: NonNullable<TaskRunsCountFilter["flows"]>;
} {
	return {
		task_runs: {
			operator: "and_",
			subflow_runs: {
				exists_: false,
			},
		},
		flows: {
			operator: "and_",
			id: {
				any_: [flowId],
			},
		},
	};
}

/**
 * Builds the filter for counting total task runs (completed, failed, crashed, running).
 */
export function buildTotalTaskRunsCountFilter(
	flowId: string,
): TaskRunsCountFilter {
	const baseFilter = buildBaseCountFilter(flowId);
	return {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: {
					any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"],
				},
			},
		},
	};
}

/**
 * Builds the filter for counting completed task runs.
 */
export function buildCompletedTaskRunsCountFilter(
	flowId: string,
): TaskRunsCountFilter {
	const baseFilter = buildBaseCountFilter(flowId);
	return {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: {
					any_: ["COMPLETED"],
				},
			},
		},
	};
}

/**
 * Builds the filter for counting failed task runs (including crashed).
 */
export function buildFailedTaskRunsCountFilter(
	flowId: string,
): TaskRunsCountFilter {
	const baseFilter = buildBaseCountFilter(flowId);
	return {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: {
					any_: ["FAILED", "CRASHED"],
				},
			},
		},
	};
}

/**
 * Builds the filter for counting running task runs.
 */
export function buildRunningTaskRunsCountFilter(
	flowId: string,
): TaskRunsCountFilter {
	const baseFilter = buildBaseCountFilter(flowId);
	return {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: {
					any_: ["RUNNING"],
				},
			},
		},
	};
}

/**
 * Gets a stable timestamp rounded to the start of the current hour.
 * This ensures query key stability between prefetch and render.
 */
function getStableHourBoundary(): Date {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	return now;
}

/**
 * Builds the filter for task runs history for a specific flow.
 * Uses stable hour-boundary timestamps to ensure query key stability with Suspense.
 */
export function buildTaskRunsHistoryFilterForFlow(
	flowId: string,
): TaskRunsHistoryFilter {
	const endDate = getStableHourBoundary();
	const startDate = new Date(endDate.getTime() - 7 * 24 * 60 * 60 * 1000);

	const history_start = startDate.toISOString();
	const history_end = endDate.toISOString();
	const timeSpanInSeconds = Math.floor(
		(endDate.getTime() - startDate.getTime()) / 1000,
	);
	const historyInterval = Math.max(1, Math.floor(timeSpanInSeconds / 20));

	return {
		history_start,
		history_end,
		history_interval_seconds: historyInterval,
		flows: {
			operator: "and_",
			id: {
				any_: [flowId],
			},
		},
		task_runs: {
			operator: "and_",
			start_time: {
				after_: history_start,
				before_: history_end,
			},
		},
	};
}
