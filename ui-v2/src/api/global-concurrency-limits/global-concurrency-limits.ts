import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type GlobalConcurrencyLimit =
	components["schemas"]["GlobalConcurrencyLimitResponse"];
export type GlobalConcurrencyLimitsFilter =
	components["schemas"]["Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post"];
export type GlobalConcurrencyLimitsCountFilter =
	components["schemas"]["Body_count_all_concurrency_limits_v2_v2_concurrency_limits_count_post"];

/**
 * ```
 *  🏗️ Global concurrency limits queries construction 👷
 *  all   =>   ['global-concurrency-limits'] // key to match ['global-concurrency-limits', ...
 *  list  =>   ['global-concurrency-limits', 'list'] // key to match ['global-concurrency-limits', 'list', ...
 *             ['global-concurrency-limits', 'list', { ...filter1 }]
 *             ['global-concurrency-limits', 'list', { ...filter2 }]
 *  listsPaginate  =>  ['global-concurrency-limits', 'list', 'paginate']
 *             ['global-concurrency-limits', 'list', 'paginate', { ...filter1 }]
 *  counts =>  ['global-concurrency-limits', 'counts'] // key to match ['global-concurrency-limits', 'counts', ...
 *             ['global-concurrency-limits', 'counts', { ...filter1 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["global-concurrency-limits"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: GlobalConcurrencyLimitsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	listsPaginate: () => [...queryKeyFactory.lists(), "paginate"] as const,
	listPaginate: (filter: GlobalConcurrencyLimitsFilter) =>
		[...queryKeyFactory.listsPaginate(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (filter: GlobalConcurrencyLimitsCountFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
};

/**
 * Builds the request body for a page of global concurrency limits
 *
 * @param options - the page number (1-based), page size and name search value
 * @returns a filter that pages and filters global concurrency limits server-side
 */
export const buildGlobalConcurrencyLimitsPaginationBody = ({
	page = 1,
	limit = 10,
	search = "",
}: {
	page?: number;
	limit?: number;
	search?: string;
}): GlobalConcurrencyLimitsFilter => ({
	limit,
	offset: (page - 1) * limit,
	concurrency_limits: {
		operator: "and_",
		name: { like_: search },
	},
});

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListGlobalConcurrencyLimitsQuery = (
	filter: GlobalConcurrencyLimitsFilter = { offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/v2/concurrency_limits/filter",
				{ body: filter },
			);
			return res.data ?? [];
		},
		refetchInterval: 30_000,
	});

/**
 * Builds a query for a page of global concurrency limits.
 *
 * The server applies the name filter and the page bounds, so the page can be
 * any page of the full set of limits.
 *
 * @param filter - the page bounds and the name filter to apply
 * @returns a queryOptions object for the requested page
 */
export const buildPaginateGlobalConcurrencyLimitsQuery = (
	filter: GlobalConcurrencyLimitsFilter = { offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.listPaginate(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/v2/concurrency_limits/filter",
				{ body: filter },
			);
			return res.data ?? [];
		},
		placeholderData: keepPreviousData,
		refetchInterval: 30_000,
	});

/**
 *
 * @param filter
 * @returns count of global concurrency limits matching the filter as a queryOptions object
 */
export const buildCountGlobalConcurrencyLimitsQuery = (
	filter: GlobalConcurrencyLimitsCountFilter = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.count(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/v2/concurrency_limits/count",
				{ body: filter },
			);
			return res.data ?? 0;
		},
		refetchInterval: 30_000,
	});

/**
 *
 * @param filter
 * @returns list of global concurrency limits as a SuspenseQueryResult object
 */

export const useListGlobalConcurrencyLimits = (
	filter: GlobalConcurrencyLimitsFilter = { offset: 0 },
) => useSuspenseQuery(buildListGlobalConcurrencyLimitsQuery(filter));

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
		mutationFn: async (id_or_name: string) =>
			(await getQueryService()).DELETE("/v2/concurrency_limits/{id_or_name}", {
				params: { path: { id_or_name } },
			}),
		onSuccess: () => {
			// After a successful deletion, invalidate the listing and count queries to refetch
			return Promise.all([
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.lists() }),
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.counts() }),
			]);
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
 *     console.error('Failed to create global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useCreateGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: createGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: async (
			body: components["schemas"]["ConcurrencyLimitV2Create"],
		) =>
			(await getQueryService()).POST("/v2/concurrency_limits/", {
				body,
			}),
		onSuccess: () => {
			// After a successful creation, invalidate the listing and count queries to refetch
			return Promise.all([
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.lists() }),
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.counts() }),
			]);
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
 *     console.error('Failed to update global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useUpdateGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: updateGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: async ({
			id_or_name,
			...body
		}: GlobalConcurrencyLimitUpdateWithId) =>
			(await getQueryService()).PATCH("/v2/concurrency_limits/{id_or_name}", {
				body,
				params: { path: { id_or_name } },
			}),
		onSuccess: () => {
			// After a successful creation, invalidate lists queries
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		updateGlobalConcurrencyLimit,
		...rest,
	};
};

/**
 * Hook for resetting a global concurrency limit's active slots to 0
 *
 * @returns Mutation object for resetting a global concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { resetGlobalConcurrencyLimit } = useResetGlobalConcurrencyLimit();
 *
 * // Reset a global concurrency limit's active slots by id or name
 * resetGlobalConcurrencyLimit('id-or-name', {
 *   onSuccess: () => {
 *     console.log('Global concurrency limit reset successfully');
 *   },
 *   onError: (error) => {
 *     console.error('Failed to reset global concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useResetGlobalConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: resetGlobalConcurrencyLimit, ...rest } = useMutation({
		mutationFn: async (id_or_name: string) =>
			(await getQueryService()).PATCH("/v2/concurrency_limits/{id_or_name}", {
				body: { active_slots: 0 },
				params: { path: { id_or_name } },
			}),
		onSuccess: () => {
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		resetGlobalConcurrencyLimit,
		...rest,
	};
};
