import { queryOptions } from "@tanstack/react-query";
import { components } from "../prefect";
import { getQueryService } from "../service";

export type TaskRun = components["schemas"]["TaskRun"];

export type TaskRunsFilter =
	components["schemas"]["Body_read_task_runs_task_runs_filter_post"];

/**
 * Query key factory for task-related queries
 *
 * @property {function} all - Returns base key for all task run queries
 * @property {function} lists - Returns key for all list-type task run queries
 * @property {function} list - Generates key for a specific filtered task run query
 *
 * ```
 * all			=>   ['task']
 * lists		=>   ['task', 'list']
 * list			=>   ['task', 'list', { ...filter }]
 * counts		=>   ['task', 'count']
 * flowRunsCount	=>   ['task', 'count', 'flow-runs', ["id-0", "id-1"]]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["taskRuns"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: TaskRunsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "count"] as const,
	flowRunsCount: (flowRunIds: Array<string>) => [
		...queryKeyFactory.counts(),
		"flow-runs",
		flowRunIds,
	],
};

/**
 * Builds a query configuration for fetching filtered task runs
 *
 * @param filter - Filter parameters for the task runs query.
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data, isLoading, error } = useQuery(buildListTaskRunsQuery({
 *   offset: 0,
 *   sort: "CREATED_DESC",
 *   task_runs: {
 *     name: { like_: "my-task-run" }
 *   }
 * }));
 * ```
 */
export const buildListTaskRunsQuery = (
	filter: TaskRunsFilter = {
		sort: "ID_DESC",
		offset: 0,
	},
	refetchInterval: number = 30_000,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/task_runs/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		staleTime: 1000,
		refetchInterval,
	});
};

/**
 * Builds a query configuration for fetching flow runs task count
 *
 * @param flow_run_ids - Array of flow run ids
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildListTaskRunsQuery(["id-0", "id-1"]));
 * ```
 */
export const buildGetFlowRunsTaskRunsCountQuery = (
	flow_run_ids: Array<string>,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.flowRunsCount(flow_run_ids),
		queryFn: async () => {
			const res = await getQueryService().POST(
				"/ui/flow_runs/count-task-runs",
				{ body: { flow_run_ids } },
			);
			return res.data ?? {};
		},
	});
};
