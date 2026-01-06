import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type Flow = components["schemas"]["Flow"];
export type FlowsFilter =
	components["schemas"]["Body_read_flows_flows_filter_post"];
export type FlowsPaginateFilter =
	components["schemas"]["Body_paginate_flows_flows_paginate_post"];
export type SimpleNextFlowRun = components["schemas"]["SimpleNextFlowRun"];

/**
 * Query key factory for flows-related queries
 *
 * @property {function} all - Returns base key for all flow queries
 * @property {function} lists - Returns key for all list-type flow queries
 * @property {function} list - Generates key for a specific filtered flow query
 * @property {function} details - Returns key for all flow details queries
 * @property {function} detail - Generates key for a specific flow details query
 *
 * ```
 * all    	=>   ['flows']
 * lists  	=>   ['flows', 'list']
 * list   	=>   ['flows', 'list', { ...filter }]
 * details  =>   ['flows', 'details']
 * detail   =>   ['flows', 'details', id]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["flows"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: FlowsFilter) => [...queryKeyFactory.lists(), filter] as const,
	paginate: (filter: FlowsPaginateFilter) =>
		[...queryKeyFactory.lists(), "paginate", filter] as const,
	details: () => [...queryKeyFactory.all(), "detail"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
	deploymentsCount: (flowIds: string[]) =>
		[
			...queryKeyFactory.all(),
			"deploymentsCount",
			[...flowIds].sort(),
		] as const,
	nextRuns: (flowIds: string[]) =>
		[...queryKeyFactory.all(), "nextRuns", [...flowIds].sort()] as const,
};

/**
 * Builds a query configuration for fetching filtered flows
 *
 * @param filter - Filter parameters for the flows query
 * @returns Query configuration object with:
 *   - queryKey: Unique key for caching
 *   - queryFn: Function to fetch the filtered flows
 *   - staleTime: Time in ms before data is considered stale
 *
 * @example
 * ```ts
 * const query = buildListFlowsQuery({
 *   flows: {
 *     operator: "and_",
 *     name: { like_: "my-flow" }
 *   }
 * });
 * const { data } = await queryClient.fetchQuery(query);
 * ```
 */
export const buildListFlowsQuery = (
	filter: FlowsFilter = { offset: 0, sort: "CREATED_DESC" },
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const result = await (await getQueryService()).POST("/flows/filter", {
				body: filter,
			});
			return result.data ?? [];
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
		enabled,
	});

/**
 * Builds a query configuration for fetching paginated flows
 *
 * @param filter - Filter parameters for the flows pagination query.
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useQuery(buildPaginateFlowsQuery({ page: 1, limit: 10 }));
 * ```
 */
export const buildPaginateFlowsQuery = (
	filter: FlowsPaginateFilter = {
		page: 1,
		sort: "NAME_ASC",
	},
	refetchInterval = 30_000,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.paginate(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/flows/paginate", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		placeholderData: keepPreviousData,
		staleTime: 1000,
		refetchInterval,
	});
};

/**
 * Builds a query configuration for getting a flow's details
 *
 * @param id - flow's id
 *
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildFLowDetailsQuery(flow_id));
 * ```
 */
export const buildFLowDetailsQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await (await getQueryService()).GET("/flows/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});

/**
 * Builds a query configuration for counting filtered flows
 * @param filter - Filter parameters for the flows query
 * @returns Query configuration object with:
 *  - queryKey: Unique key for caching
 * - queryFn: Function to fetch the filtered flows
 * - staleTime: Time in ms before data is considered stale
 * @example
 * ```ts
 * const query = buildCountFlowsFilteredQuery({
 *  flows: {
 *   operator: "and_",
 *  name: { like_: "my-flow" }
 * }
 * });
 * const { data } = await queryClient.fetchQuery(query);
 * ```
 * */
export const buildCountFlowsFilteredQuery = (filter: FlowsFilter) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const result = await (await getQueryService()).POST("/flows/count", {
				body: filter,
			});
			return result.data ?? 0;
		},
	});

/**
 * Builds a query configuration for fetching deployment counts by flow ID
 *
 * @param flowIds - Array of flow IDs to get deployment counts for
 * @param options - Optional configuration with enabled flag
 * @returns Query configuration object with:
 *   - queryKey: Unique key for caching (sorted flowIds for consistency)
 *   - queryFn: Function to fetch deployment counts
 *   - enabled: Whether the query should run (defaults to flowIds.length > 0)
 *
 * @example
 * ```ts
 * const query = buildDeploymentsCountByFlowQuery(['flow-id-1', 'flow-id-2']);
 * const { data } = useQuery(query);
 * // data: { 'flow-id-1': 5, 'flow-id-2': 3 }
 * ```
 */
export const buildDeploymentsCountByFlowQuery = (
	flowIds: string[],
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.deploymentsCount(flowIds),
		queryFn: async () => {
			const result = await (await getQueryService()).POST(
				"/ui/flows/count-deployments",
				{
					body: { flow_ids: flowIds },
				},
			);
			return (result.data ?? {}) as Record<string, number>;
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
		enabled: enabled && flowIds.length > 0,
	});

/**
 * Builds a query configuration for fetching next scheduled runs by flow ID
 *
 * @param flowIds - Array of flow IDs to get next runs for
 * @param options - Optional configuration with enabled flag
 * @returns Query configuration object with:
 *   - queryKey: Unique key for caching (sorted flowIds for consistency)
 *   - queryFn: Function to fetch next runs
 *   - enabled: Whether the query should run (defaults to flowIds.length > 0)
 *
 * @example
 * ```ts
 * const query = buildNextRunsByFlowQuery(['flow-id-1', 'flow-id-2']);
 * const { data } = useQuery(query);
 * // data: { 'flow-id-1': { id: '...', name: '...', ... }, 'flow-id-2': null }
 * ```
 */
export const buildNextRunsByFlowQuery = (
	flowIds: string[],
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.nextRuns(flowIds),
		queryFn: async () => {
			const result = await (await getQueryService()).POST(
				"/ui/flows/next-runs",
				{
					body: { flow_ids: flowIds },
				},
			);
			return (result.data ?? {}) as Record<string, SimpleNextFlowRun | null>;
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
		enabled: enabled && flowIds.length > 0,
	});

/**
 * Hook for deleting a flow
 *
 * @returns Mutation object for deleting a flow with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteDeploymentSchedule } = useDeleteDeploymentSchedule();
 *
 * deleteDeploymentSchedule({deployment_id, schedule_id, ...body}, {
 *   onSuccess: () => {
 *     // Handle successful update
 *     console.log('Deployment schedule deleted successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to delete deployment schedule:', error);
 *   }
 * });
 * ```
 */
export const useDeleteFlowById = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteFlow, ...rest } = useMutation({
		mutationFn: async (id: string) =>
			(await getQueryService()).DELETE("/flows/{id}", {
				params: { path: { id } },
			}),
		onSettled: () =>
			queryClient.invalidateQueries({ queryKey: queryKeyFactory.all() }),
	});

	return { deleteFlow, ...rest };
};
