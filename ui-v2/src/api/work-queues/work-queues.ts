import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions } from "@tanstack/react-query";

export type WorkQueue = components["schemas"]["WorkQueueResponse"];
export type WorkQueuesFilter =
	components["schemas"]["Body_read_work_queues_work_queues_filter_post"];

/**
 * Query key factory for work queues-related queries
 *
 * @property {function} all - Returns base key for all work queue queries
 * @property {function} lists - Returns key for all list-type work queue queries
 * @property {function} list - Generates key for specific filtered work queue queries

 *
 * ```
 * all    =>   ['work-queues']
 * lists  =>   ['work-queues', 'list']
 * list   =>   ['work-queues', 'list', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["work-queues"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: WorkQueuesFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching filtered work queues
 *
 * @param filter - Filter options including:
 *   - limit: Number of items per page (default: 10)
 *   - offset: Offset of results based on the limit
 *   - work_queues: Optional work queues-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildFilterWorkQueuesQuery({
 *   limit: 100,
 *   offset: 0
 * }));
 * ```
 */
export const buildFilterWorkQueuesQuery = (
	filter: WorkQueuesFilter = { offset: 0 },
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/work_queues/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		enabled,
	});
