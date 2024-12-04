import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQuery,
	useQueryClient,
} from "@tanstack/react-query";

export type GlobalConcurrencyLimit =
	components["schemas"]["GlobalConcurrencyLimitResponse"];
export type GlobalConcurrencyLimitsFilter =
	components["schemas"]["Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post"];

/**
 * ```
 *  🏗️ Global concurrency limits queries construction 👷
 *  all   =>   ['global-concurrency-limits'] // key to match ['global-concurrency-limits', ...
 *  list  =>   ['global-concurrency-limits', 'list'] // key to match ['global-concurrency-limits', 'list', ...
 *             ['global-concurrency-limits', 'list', { ...filter1 }]
 *             ['global-concurrency-limits', 'list', { ...filter2 }]
 *  details => ['global-concurrency-limits', 'details'] // key to match ['global-concurrency-limits', 'details', ...]
 *             ['global-concurrency-limits', 'details', { ...globalConcurrencyLimit1 }]
 *             ['global-concurrency-limits', 'details', { ...globalConcurrencyLimit2 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["global-concurrency-limits"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: GlobalConcurrencyLimitsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id_or_name: string) =>
		[...queryKeyFactory.details(), id_or_name] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListGlobalConcurrencyLimitsQuery = (
	filter: GlobalConcurrencyLimitsFilter,
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST(
				"/v2/concurrency_limits/filter",
				{ body: filter },
			);
			return res.data ?? [];
		},
	});

export const buildGetGlobalConcurrencyLimitQuery = (id_or_name: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id_or_name),
		queryFn: async () => {
			const res = await getQueryService().GET(
				"/v2/concurrency_limits/{id_or_name}",
				{ params: { path: { id_or_name } } },
			);
			return res.data ?? null;
		},
	});

/**
 *
 * @param filter
 * @returns list of global concurrency limits as a QueryResult object
 */
export const useListGlobalConcurrencyLimits = (
	filter: GlobalConcurrencyLimitsFilter,
) => useQuery(buildListGlobalConcurrencyLimitsQuery(filter));

/**
 *
 * @param id_or_name
 * @returns details about the specified global concurrency limit as a QueryResult object
 */
export const useGetGlobalConcurrencyLimit = (id_or_name: string) =>
	useQuery(buildGetGlobalConcurrencyLimitQuery(id_or_name));

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

/**
 * Hook for deleting a global concurrency limit
 *
 * @returns Mutation object for deleting a global concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteGlobalConcurrencyLimit } = useDeleteGlobalConcurrencyLimit();
 *
 * // Delete a  global concurrency limit by id or name
 * deleteGlobalConcurrencyLimit('id-to-delete', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *   },
 *   onError: (error) => {
 *     console.error('Failed to delete global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useDeleteGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: deleteGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: (id_or_name: string) =>
			getQueryService().DELETE("/v2/concurrency_limits/{id_or_name}", {
				params: { path: { id_or_name } },
			}),
		onSuccess: () => {
			// After a successful deletion, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		deleteGlobalConcurrencyLimit,
		...rest,
	};
};

/**
 * Hook for creating a new global concurrency limit
 *
 * @returns Mutation object for creating a global concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createGlobalConcurrencyLimit, isLoading } = useCreateGlobalConcurrencyLimit();
 *
 * // Create a new  global concurrency limit
 * createGlobalConcurrencyLimit({
 * 	active: true
 * 	limit: 0
 * 	name: "my limit"
 * 	slot_decay_per_second: 0
 * }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Global concurrency limit created successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useCreateGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: createGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: (body: components["schemas"]["ConcurrencyLimitV2Create"]) =>
			getQueryService().POST("/v2/concurrency_limits/", {
				body,
			}),
		onSuccess: () => {
			// After a successful creation, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		createGlobalConcurrencyLimit,
		...rest,
	};
};

type GlobalConcurrencyLimitUpdateWithId =
	components["schemas"]["ConcurrencyLimitV2Update"] & {
		id_or_name: string;
	};

/**
 * Hook for updating an existing global concurrency limit
 *
 * @returns Mutation object for updating a global concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { udateGlobalConcurrencyLimit } = useUpdateGlobalConcurrencyLimit();
 *
 * // Update an existing  global concurrency limit
 * updateGlobalConcurrencyLimit({
 *  id_or_name: "1",
 * 	active: true
 * 	limit: 0
 * 	name: "my limit"
 * 	slot_decay_per_second: 0
 * }, {
 *   onSuccess: () => {
 *     // Handle successful update
 *   },
 *   onError: (error) => {
 *     console.error('Failed to update  global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useUpdateGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: updateGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: ({ id_or_name, ...body }: GlobalConcurrencyLimitUpdateWithId) =>
			getQueryService().PATCH("/v2/concurrency_limits/{id_or_name}", {
				body,
				params: { path: { id_or_name } },
			}),
		onSuccess: (_, { id_or_name }) => {
			// After a successful creation, invalidate lists and sepecfic details queries
			return Promise.all([
				// list queries
				queryClient.invalidateQueries({
					queryKey: queryKeyFactory.lists(),
				}),
				// Specific limit details
				queryClient.invalidateQueries({
					queryKey: queryKeyFactory.detail(id_or_name),
				}),
			]);
		},
	});
	return {
		updateGlobalConcurrencyLimit,
		...rest,
	};
};
