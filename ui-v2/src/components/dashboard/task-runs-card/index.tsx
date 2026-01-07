import { useQuery } from "@tanstack/react-query";
import { Suspense, useMemo } from "react";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountTaskRunsQuery,
	type TaskRunsCountFilter,
} from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardErrorState } from "@/components/ui/card-error-state";
import { TaskRunsCardSkeleton } from "./task-runs-card-skeleton";
import { TaskRunsTrends } from "./task-runs-trends";

// Re-exports are in a separate file to avoid react-refresh/only-export-components warning
// See: ./exports.ts for buildTaskRunsHistoryFilterFromDashboard, TaskRunsTrendsFilter, TaskRunStats, TaskRunsTrends

type TaskRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
};

/**
 * Builds a base filter for task run count queries that matches the Vue implementation.
 * This includes:
 * - Date range filtering on task_runs.start_time
 * - Excluding subflow task runs (task_runs.subflow_runs.exists_ = false)
 * - Tag filtering on flow_runs.tags.any_ (matching Vue's anyName behavior)
 * - Hide subflows filtering on flow_runs.parent_task_run_id.is_null_
 */
function buildBaseCountFilter(filter?: TaskRunsCardProps["filter"]): {
	task_runs: NonNullable<TaskRunsCountFilter["task_runs"]>;
	flow_runs?: NonNullable<TaskRunsCountFilter["flow_runs"]>;
} {
	const taskRunsFilter: NonNullable<TaskRunsCountFilter["task_runs"]> = {
		operator: "and_",
		// Exclude subflow task runs by default (matches Vue's getBaseFilter)
		subflow_runs: {
			exists_: false,
		},
	};

	// Add date range filter
	if (filter?.startDate && filter?.endDate) {
		taskRunsFilter.start_time = {
			after_: filter.startDate,
			before_: filter.endDate,
		};
	}

	const result: {
		task_runs: NonNullable<TaskRunsCountFilter["task_runs"]>;
		flow_runs?: NonNullable<TaskRunsCountFilter["flow_runs"]>;
	} = {
		task_runs: taskRunsFilter,
	};

	// Add flow_runs filter for tags and hideSubflows (matching Vue's dashboard mapping)
	if ((filter?.tags && filter.tags.length > 0) || filter?.hideSubflows) {
		const flowRunsFilter: NonNullable<TaskRunsCountFilter["flow_runs"]> = {
			operator: "and_",
		};

		// Tags filter on flow_runs (matching Vue's flowRuns.tags.anyName)
		if (filter?.tags && filter.tags.length > 0) {
			flowRunsFilter.tags = {
				operator: "and_",
				any_: filter.tags,
			};
		}

		// Hide subflows filter (matching Vue's flowRuns.parentTaskRunIdNull)
		if (filter?.hideSubflows) {
			flowRunsFilter.parent_task_run_id = {
				operator: "and_",
				is_null_: true,
			};
		}

		result.flow_runs = flowRunsFilter;
	}

	return result;
}

export function TaskRunsCard({ filter }: TaskRunsCardProps) {
	// Build base filter that's shared across all count queries
	const baseFilter = useMemo(() => buildBaseCountFilter(filter), [filter]);

	// Build filters for each state type (matching Vue's CumulativeTaskRunsCard)
	const totalFilter: TaskRunsCountFilter = useMemo(
		() => ({
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
		}),
		[baseFilter],
	);

	const completedFilter: TaskRunsCountFilter = useMemo(
		() => ({
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
		}),
		[baseFilter],
	);

	const failedFilter: TaskRunsCountFilter = useMemo(
		() => ({
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
		}),
		[baseFilter],
	);

	const runningFilter: TaskRunsCountFilter = useMemo(
		() => ({
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
		}),
		[baseFilter],
	);

	// Fetch counts using the count endpoint (matching Vue's useTaskRunsCount)
	const totalQuery = useQuery(buildCountTaskRunsQuery(totalFilter, 30_000));
	const completedQuery = useQuery(
		buildCountTaskRunsQuery(completedFilter, 30_000),
	);
	const failedQuery = useQuery(buildCountTaskRunsQuery(failedFilter, 30_000));
	const runningQuery = useQuery(buildCountTaskRunsQuery(runningFilter, 30_000));

	// Combine all query errors - if any critical query fails, show error
	const criticalQueries = [
		totalQuery,
		completedQuery,
		failedQuery,
		runningQuery,
	];

	const failedQueryResult = criticalQueries.find((q) => q.isError);
	if (failedQueryResult) {
		return (
			<CardErrorState
				error={categorizeError(
					failedQueryResult.error,
					"Failed to load task runs",
				)}
				onRetry={() => {
					criticalQueries
						.filter((q) => q.isError)
						.forEach((q) => void q.refetch());
				}}
				isRetrying={criticalQueries.some((q) => q.isRefetching)}
			/>
		);
	}

	// Show loading state while critical data is loading
	const isCriticalLoading = criticalQueries.some((q) => q.isLoading);
	if (isCriticalLoading) {
		return <TaskRunsCardSkeleton />;
	}

	// Extract data from queries with defaults
	const total = totalQuery.data ?? 0;
	const completed = completedQuery.data ?? 0;
	const failed = failedQuery.data ?? 0;
	const running = runningQuery.data ?? 0;

	// Calculate failure percentage (matching Vue's percentComparisonTotal logic)
	// Vue excludes running from the denominator for percentage calculations
	const percentComparisonTotal = total - running;
	const failurePercentage =
		percentComparisonTotal > 0 ? (failed / percentComparisonTotal) * 100 : 0;

	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle>Task Runs</CardTitle>
			</CardHeader>
			<CardContent>
				<div className="space-y-4">
					<div className="grid gap-1">
						<div className="inline-flex items-end gap-1 text-base">
							<span className="font-semibold">{total}</span>
						</div>
						{running > 0 && (
							<div className="inline-flex items-end gap-1 text-sm">
								<span className="font-semibold">{running}</span>
								<span className="text-muted-foreground">Running</span>
							</div>
						)}
						<div className="inline-flex items-end gap-1 text-sm">
							<span className="font-semibold">{completed}</span>
							<span className="text-muted-foreground">Completed</span>
						</div>
						{failed > 0 && (
							<div className="inline-flex items-end gap-1 text-sm">
								<span className="font-semibold">{failed}</span>
								<span className="text-muted-foreground">Failed</span>
								<span className="text-muted-foreground">
									{failurePercentage.toFixed(1)}%
								</span>
							</div>
						)}
					</div>
					<Suspense fallback={null}>
						<TaskRunsTrends filter={filter} />
					</Suspense>
				</div>
			</CardContent>
		</Card>
	);
}
