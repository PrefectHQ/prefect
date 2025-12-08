import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type SavedSearch = components["schemas"]["SavedSearch"];
export type SavedSearchCreate = components["schemas"]["SavedSearchCreate"];
export type SavedSearchFilter = components["schemas"]["SavedSearchFilter"];

/**
 * Query key factory for saved-searches-related queries
 *
 * @property {function} all - Returns base key for all saved search queries
 * @property {function} lists - Returns key for all list-type saved search queries
 * @property {function} list - Generates key for a specific filtered saved search query
 *
 * ```
 * all    	=>   ['savedSearches']
 * lists  	=>   ['savedSearches', 'list']
 * list   	=>   ['savedSearches', 'list', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["savedSearches"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter?: { offset?: number; limit?: number }) =>
		[...queryKeyFactory.lists(), filter] as const,
};

/**
 * Builds a query configuration for fetching saved searches
 *
 * @param filter - Optional filter parameters for the saved searches query
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildListSavedSearchesQuery());
 * ```
 */
export const buildListSavedSearchesQuery = (
	filter: { offset?: number; limit?: number } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const result = await getQueryService().POST("/saved_searches/filter", {
				body: filter,
			});
			return result.data ?? [];
		},
		staleTime: 30_000,
	});

/**
 * Hook for creating a saved search
 *
 * @returns Mutation object for creating a saved search with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createSavedSearch, isPending } = useCreateSavedSearch();
 *
 * createSavedSearch({ name: "My Filter", filters: [...] }, {
 *   onSuccess: () => {
 *     console.log('Saved search created successfully');
 *   },
 *   onError: (error) => {
 *     console.error('Failed to create saved search:', error);
 *   }
 * });
 * ```
 */
export const useCreateSavedSearch = () => {
	const queryClient = useQueryClient();

	const { mutate: createSavedSearch, ...rest } = useMutation({
		mutationFn: async (body: SavedSearchCreate) => {
			const res = await getQueryService().PUT("/saved_searches/", {
				body,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		onSuccess: () => {
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});

	return { createSavedSearch, ...rest };
};

/**
 * Hook for deleting a saved search
 *
 * @returns Mutation object for deleting a saved search with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteSavedSearch, isPending } = useDeleteSavedSearch();
 *
 * deleteSavedSearch(id, {
 *   onSuccess: () => {
 *     console.log('Saved search deleted successfully');
 *   },
 *   onError: (error) => {
 *     console.error('Failed to delete saved search:', error);
 *   }
 * });
 * ```
 */
export const useDeleteSavedSearch = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteSavedSearch, ...rest } = useMutation({
		mutationFn: async (id: string) => {
			await getQueryService().DELETE("/saved_searches/{id}", {
				params: { path: { id } },
			});
		},
		onSuccess: () => {
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});

	return { deleteSavedSearch, ...rest };
};
