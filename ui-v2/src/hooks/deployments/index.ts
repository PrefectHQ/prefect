import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	type QueryClient,
	queryOptions,
	useSuspenseQuery,
} from "@tanstack/react-query";

export type Deployment = components["schemas"]["DeploymentResponse"];
export type DeploymentsFilter =
	components["schemas"]["Body_read_deployments_deployments_filter_post"];
export type DeploymentsPaginationFilter =
	components["schemas"]["Body_paginate_deployments_deployments_paginate_post"];

/**
 * Query key factory for deployments-related queries
 *
 * @property {function} all - Returns base key for all deployment queries
 * @property {function} lists - Returns key for all list-type deployment queries
 * @property {function} list - Generates key for specific filtered deployment queries
 * @property {function} counts - Returns key for all count-type deployment queries
 * @property {function} count - Generates key for specific filtered count queries
 *
 * ```
 * all    =>   ['deployments']
 * lists  =>   ['deployments', 'list']
 * list   =>   ['deployments', 'list', { ...filter }]
 * counts =>   ['deployments', 'counts']
 * count  =>   ['deployments', 'counts', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["deployments"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: DeploymentsFilter | DeploymentsPaginationFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (filter: DeploymentsFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching paginated deployments
 *
 * @param filter - Pagination and filter options including:
 *   - page: Page number to fetch (default: 1)
 *   - limit: Number of items per page (default: 10)
 *   - sort: Sort order for results (default: "NAME_ASC")
 *   - deployments: Optional deployment-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildPaginateDeploymentsQuery({
 *   page: 2,
 *   limit: 25,
 *   sort: "CREATED_DESC"
 * });
 * ```
 */
export const buildPaginateDeploymentsQuery = (
	filter: DeploymentsPaginationFilter = {
		page: 1,
		limit: 10,
		sort: "NAME_ASC",
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/deployments/paginate", {
				body: filter,
			});
			return res.data ?? [];
		},
	});

/**
 * Builds a query configuration for counting deployments based on filter criteria
 *
 * @param filter - Filter options for the deployments count query including:
 *   - offset: Number of items to skip (default: 0)
 *   - sort: Sort order for results (default: "NAME_ASC")
 *   - deployments: Optional deployment-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildCountDeploymentsQuery({
 *   offset: 0,
 *   limit: 10,
 *   sort: "NAME_ASC",
 *   deployments: {
 *     name: { like_: "my-deployment" }
 *   }
 * });
 * ```
 */
export const buildCountDeploymentsQuery = (
	filter: DeploymentsFilter = { offset: 0, sort: "NAME_ASC" },
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/deployments/count", {
				body: filter,
			});
			return res.data ?? [];
		},
	});

// ----------------------------
//  Queries
// ----------------------------

/**
 * Hook for fetching paginated deployments with suspense
 *
 * @param filter - Pagination and filter options for the deployments query
 * @returns SuspenseQueryResult containing the paginated deployments data
 *
 * @example
 * ```ts
 * const { data: deployments } = usePaginateDeployments({
 *   page: 1,
 *   limit: 25,
 *   sort: "NAME_ASC",
 *   deployments: {
 *     name: { like_: "my-deployment" }
 *   }
 * });
 * ```
 */
export const usePaginateDeployments = (
	filter: DeploymentsPaginationFilter = {
		page: 1,
		limit: 10,
		sort: "NAME_ASC",
	},
) => useSuspenseQuery(buildPaginateDeploymentsQuery(filter));

/**
 * Data loader for the usePaginateDeployments hook, used by TanStack Router
 * Prefetches paginated deployments data
 *
 * @param deps - Filter options to use for prefetching deployments
 * @param context - Router context containing queryClient
 * @returns Promise that resolves when deployments data is prefetched
 */
usePaginateDeployments.loader = ({
	context,
	deps,
}: {
	deps: DeploymentsPaginationFilter;
	context: { queryClient: QueryClient };
}) => context.queryClient.ensureQueryData(buildPaginateDeploymentsQuery(deps));

/**
 * Hook for fetching the count of deployments based on filter criteria with suspense
 *
 * @param filter - Filter options for the deployments count query
 * @returns SuspenseQueryResult containing the count of deployments
 *
 * @example
 * ```ts
 * const { data: count } = useCountDeployments({
 *   deployments: { name: { like_: "my-deployment" } }
 * });
 * ```
 */
export const useCountDeployments = (
	filter: DeploymentsFilter = { offset: 0, sort: "NAME_ASC" },
) => useSuspenseQuery(buildCountDeploymentsQuery(filter));

/**
 * Data loader for the useCountDeployments hook, used by TanStack Router
 * Prefetches count of deployments
 *
 * @param deps - Filter options to use for prefetching deployments
 * @param context - Router context containing queryClient
 * @returns Promise that resolves when deployments data is prefetched
 */
useCountDeployments.loader = ({
	context,
	deps,
}: {
	deps: DeploymentsFilter;
	context: { queryClient: QueryClient };
}) => context.queryClient.ensureQueryData(buildCountDeploymentsQuery(deps));
