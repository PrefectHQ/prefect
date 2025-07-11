import { queryOptions } from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type WorkQueue = components["schemas"]["WorkQueueResponse"];
export type WorkQueuesFilter =
	components["schemas"]["Body_read_work_queues_work_queues_filter_post"];
export type WorkPookWorkQueuesFilter =
	components["schemas"]["Body_read_workers_work_pools__work_pool_name__workers_filter_post"];
/**
 * Query key factory for work queues-related queries
 *
 * @property {function} all - Returns base key for all work queue queries
 * @property {function} lists - Returns key for all list-type work queue queries
 * @property {function} list - Generates key for specific filtered work queue queries

 *
 * ```
 * all				=> 	['work-queues']
 * lists 			=> 	['work-queues', 'list']
 * filters 			=> 	['work-queues', 'list', 'filters']
 * filter			=> 	['work-queues', 'list', 'filters', { ...filters }]
 * workPoolFilters	=>  ['work-queues', 'list', 'filters', workPoolName, { ...filters }]
 * details			=> 	['work-queues', 'details']
 * detail			=> 	['work-queues', 'detail', workPoolName, workQueueName]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["work-queues"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	filters: () => [...queryKeyFactory.lists(), "filter"] as const,
	filter: (filter: WorkQueuesFilter) =>
		[...queryKeyFactory.filters(), filter] as const,
	workPoolFilters: (workPoolName: string, filters: WorkPookWorkQueuesFilter) =>
		[...queryKeyFactory.filters(), workPoolName, { ...filters }] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (workPoolName: string, workQueueName: string) =>
		[...queryKeyFactory.details(), workPoolName, workQueueName] as const,
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
		queryKey: queryKeyFactory.filter(filter),
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

type BuildFilterWorkPoolWorkQueuesQuery = {
	filter?: WorkPookWorkQueuesFilter;
	work_pool_name: string | null | undefined;
};

/**
 * Builds a query configuration for fetching filtered work queues by work pool name
 *
 * @param filter - Filter options including:
 *   - limit: Number of items per page (default: 10)
 *   - offset: Offset of results based on the limit
 *   - work_queues: Optional work queues-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildFilterWorkPoolWorkQueuesQuery({
 *   work_pool_name: 'my-work-pool',
 *   limit: 100,
 *   offset: 0
 * }));
 * ```
 */
export const buildFilterWorkPoolWorkQueuesQuery = ({
	filter = { offset: 0 },
	work_pool_name,
}: BuildFilterWorkPoolWorkQueuesQuery) =>
	queryOptions({
		queryKey: queryKeyFactory.workPoolFilters(work_pool_name ?? "", filter),
		queryFn: async () => {
			const res = await getQueryService().POST(
				"/work_pools/{work_pool_name}/queues/filter",
				{
					params: { path: { work_pool_name: work_pool_name ?? "" } },
					body: filter,
				},
			);
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		enabled: Boolean(work_pool_name),
	});

/**
 * Builds a query configuration for fetching a work queue's details
 *
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildWorkQueueDetailsQuery('my-work-pool', 'my-work-queue')));
 * ```
 */
export const buildWorkQueueDetailsQuery = (
	work_pool_name: string,
	name: string,
) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(work_pool_name, name),
		queryFn: async () => {
			const res = await getQueryService().GET(
				"/work_pools/{work_pool_name}/queues/{name}",
				{ params: { path: { work_pool_name, name } } },
			);
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
