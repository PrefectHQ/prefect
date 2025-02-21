import { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { keepPreviousData, queryOptions } from "@tanstack/react-query";

export type Flow = components["schemas"]["Flow"];
export type FlowsFilter =
	components["schemas"]["Body_read_flows_flows_filter_post"];

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
	details: () => [...queryKeyFactory.all(), "detail"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
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
			const result = await getQueryService().POST("/flows/filter", {
				body: filter,
			});
			return result.data ?? [];
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
		enabled,
	});

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
			const res = await getQueryService().GET("/flows/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
