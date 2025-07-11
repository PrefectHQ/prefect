import {
	infiniteQueryOptions,
	keepPreviousData,
	queryOptions,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "../service";

type LogsFilter = components["schemas"]["Body_read_logs_logs_filter_post"];

/**
 * Query key factory for logs-related queries
 *
 * @property {function} all - Returns base key for all flow queries
 * @property {function} lists - Returns key for all list-type flow queries
 * @property {function} list - Generates key for a specific filtered flow query
 *
 * ```
 * all    	=>   ['logs']
 * lists  	=>   ['logs', 'list']
 * list   	=>   ['logs', 'list', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["logs"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: LogsFilter) => [...queryKeyFactory.lists(), filter] as const,
	infiniteLists: () => [...queryKeyFactory.lists(), "infinite"] as const,
	infiniteList: (filter: Omit<LogsFilter, "offset">) =>
		[...queryKeyFactory.infiniteLists(), filter] as const,
};

/**
 * Builds a query configuration for fetching filtered logs
 *
 * @param filter - Filter options for the logs query including:
 *   - limit: Number of logs to fetch
 *   - offset: Starting index of the logs
 *   - sort: Sort order for the logs
 *   - logs: Filter criteria for the logs
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildFilterLogsQuery({
 *   logs: {
 *     level: { ge_: 0 },
 *     task_run_id: { any_: ["f96e6054-65f7-4921-b2a5-d8827c72b708"] }
 *   },
 *   sort: "TIMESTAMP_ASC",
 *   offset: 0,
 *   limit: 200
 * }));
 * ```
 */
export const buildFilterLogsQuery = (filter: LogsFilter) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/logs/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
	});

export const buildInfiniteFilterLogsQuery = (
	filter: Omit<LogsFilter, "offset">,
) =>
	infiniteQueryOptions({
		queryKey: queryKeyFactory.infiniteList(filter),
		queryFn: async ({ pageParam = { offset: 0 } }) => {
			const res = await getQueryService().POST("/logs/filter", {
				body: { ...filter, offset: pageParam.offset },
			});
			return res.data ?? [];
		},
		initialPageParam: { offset: 0 },
		getNextPageParam: (lastPage, pages) => {
			if (lastPage.length === 0) {
				return;
			}
			return { offset: pages.reduce((sum, page) => sum + page.length, 0) };
		},
		placeholderData: keepPreviousData,
	});
