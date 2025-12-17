import { queryOptions } from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type FlowRunHistoryFilter =
	components["schemas"]["Body_read_flow_run_history_ui_flow_runs_history_post"];

export type SimpleFlowRun = components["schemas"]["SimpleFlowRun"];

/**
 * Query key factory for flow run history queries
 *
 * @property {function} history - Returns base key for all flow run history queries
 * @property {function} historyWithFilter - Generates key for a specific filtered flow run history query
 *
 * ```
 * history           => ['flowRuns', 'history']
 * historyWithFilter => ['flowRuns', 'history', {...filters}]
 * ```
 */
export const historyQueryKeys = {
	history: () => ["flowRuns", "history"] as const,
	historyWithFilter: (filter: FlowRunHistoryFilter) =>
		[...historyQueryKeys.history(), filter] as const,
};

/**
 * Builds a query configuration for fetching flow run history for scatter plot visualization
 *
 * @param filter - Filter parameters for the flow run history query.
 * @param refetchInterval - Interval for refetching the history (default 30 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: history } = useSuspenseQuery(buildFlowRunHistoryQuery({
 *   sort: "EXPECTED_START_TIME_DESC",
 *   limit: 1000
 * }));
 * ```
 */
export const buildFlowRunHistoryQuery = (
	filter: FlowRunHistoryFilter = {
		sort: "EXPECTED_START_TIME_DESC",
		limit: 1000,
		offset: 0,
	},
	refetchInterval = 30_000,
) =>
	queryOptions({
		queryKey: historyQueryKeys.historyWithFilter(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/ui/flow_runs/history", {
				body: filter,
			});
			return res.data ?? ([] satisfies SimpleFlowRun[]);
		},
		staleTime: 1000,
		refetchInterval,
	});
