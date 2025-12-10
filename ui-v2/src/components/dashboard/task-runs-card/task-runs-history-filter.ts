import type { TaskRunsHistoryFilter } from "@/api/task-runs";

export type TaskRunsTrendsFilter = {
	startDate?: string;
	endDate?: string;
	tags?: string[];
	hideSubflows?: boolean;
};

/**
 * Builds the task runs history filter from dashboard filter props.
 * This is exported so it can be reused by the dashboard route loader
 * to prefetch the same query with identical query keys.
 */
export function buildTaskRunsHistoryFilterFromDashboard(
	filter?: TaskRunsTrendsFilter,
): TaskRunsHistoryFilter {
	const now = new Date();
	const startDate = filter?.startDate
		? new Date(filter.startDate)
		: new Date(now.getTime() - 24 * 60 * 60 * 1000);
	const endDate = filter?.endDate ? new Date(filter.endDate) : now;

	const history_start = startDate.toISOString();
	const history_end = endDate.toISOString();
	const timeSpanInSeconds = Math.floor(
		(endDate.getTime() - startDate.getTime()) / 1000,
	);
	const historyInterval = Math.max(1, Math.floor(timeSpanInSeconds / 20));

	// Build filter matching Vue's mapTaskRunsHistoryFilter
	// Vue always includes flow_runs and task_runs with start_time filter
	const baseFilter: TaskRunsHistoryFilter = {
		history_start,
		history_end,
		history_interval_seconds: historyInterval,
		// Always include flow_runs (matches Vue's behavior - empty object when no filters)
		flow_runs: {
			operator: "and_",
		},
		// Always include task_runs with start_time filter (matches Vue's mapTaskRunFilter)
		task_runs: {
			operator: "and_",
			start_time: {
				after_: history_start,
				before_: history_end,
			},
		},
	};

	// Add tags filter on flow_runs (matching Vue's flowRuns.tags.anyName)
	if (filter?.tags && filter.tags.length > 0) {
		baseFilter.flow_runs = {
			operator: "and_",
			...baseFilter.flow_runs,
			tags: {
				operator: "and_",
				any_: filter.tags,
			},
		};
	}

	// Add hideSubflows filter (matching Vue's flowRuns.parentTaskRunIdNull)
	if (filter?.hideSubflows) {
		baseFilter.flow_runs = {
			operator: "and_",
			...baseFilter.flow_runs,
			parent_task_run_id: {
				operator: "and_",
				is_null_: true,
			},
		};
	}

	return baseFilter;
}
