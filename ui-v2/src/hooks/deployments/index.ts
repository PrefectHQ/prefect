import {
	DeploymentsFilter,
	DeploymentsPaginationFilter,
	buildCountDeploymentsQuery,
	buildPaginateDeploymentsQuery,
} from "@/api/deployments";
import { type QueryClient, useSuspenseQuery } from "@tanstack/react-query";

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
