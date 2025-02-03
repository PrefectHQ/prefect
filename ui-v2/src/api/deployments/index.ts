import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";

export type Deployment = components["schemas"]["DeploymentResponse"];
export type DeploymentWithFlow = Deployment & {
	flow?: components["schemas"]["Flow"];
};
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
 * all				=>   ['deployments']
 * lists			=>   ['deployments', 'list']
 * lists-paginate	=>   ['deployments', 'list', 'paginate']
 * list-paginate	=>   ['deployments', 'list', 'paginate', { ...filter }]
 * lists-filter		=>   ['deployments', 'list', 'filter']
 * list-filter		=>   ['deployments', 'list', 'filter', { ...filter }]
 * counts			=>   ['deployments', 'counts']
 * count			=>   ['deployments', 'counts', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["deployments"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	"lists-paginate": () => [...queryKeyFactory.lists(), "paginate"] as const,
	"list-paginate": (filter: DeploymentsPaginationFilter) =>
		[...queryKeyFactory["lists-paginate"](), filter] as const,
	"lists-filter": () => [...queryKeyFactory.lists(), "filter"] as const,
	"list-filter": (filter: DeploymentsFilter) =>
		[...queryKeyFactory["lists-filter"](), filter] as const,
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
		queryKey: queryKeyFactory["list-paginate"](filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/deployments/paginate", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for fetching filtered deployments
 *
 * @param filter - Pagination and filter options including:
 *   - sort: Sort order for results (default: "NAME_ASC")
 *   - offset: offset number of the payload being sent
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildFilterDeploymentsQuery({
 *   offset: 0,
 *   sort: "CREATED_DESC"
 * });
 * ```
 */
export const buildFilterDeploymentsQuery = (
	filter: DeploymentsFilter = {
		offset: 0,
		sort: "CREATED_DESC",
	},
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory["list-filter"](filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/deployments/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		placeholderData: keepPreviousData,
		enabled,
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
		queryKey: queryKeyFactory.count(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/deployments/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
	});

// ----------------------------
// --------  Mutations --------
// ----------------------------

/**
 * Hook for deleting a deployment
 *
 * @returns Mutation object for deleting a deployment with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteDeployment } = useDeleteDeployment();
 *
 * // Delete a deployment by id
 * deleteDeployment('deployment-id', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *     console.log('Deployment deleted successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to delete deployment:', error);
 *   }
 * });
 * ```
 */
export const useDeleteDeployment = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteDeployment, ...rest } = useMutation({
		mutationFn: (id: string) =>
			getQueryService().DELETE("/deployments/{id}", {
				params: { path: { id } },
			}),
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});

	return { deleteDeployment, ...rest };
};
