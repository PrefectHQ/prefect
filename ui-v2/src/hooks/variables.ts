import {
	keepPreviousData,
	type QueryClient,
	queryOptions,
	useMutation,
	useQueries,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

type VariablesFilter =
	components["schemas"]["Body_read_variables_variables_filter_post"];

export const queryKeyFactory = {
	all: () => ["variables"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	listsFilter: () => [...queryKeyFactory.lists(), "filter"] as const,
	listFilter: (filter: VariablesFilter) =>
		[...queryKeyFactory.listsFilter(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	countsAll: () => [...queryKeyFactory.counts(), "all"] as const,
	count: (filter: VariablesFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
};

/**
 * Builds a query configuration for fetching filtered variables
 * @param options - Filter options for the variables query including pagination, sorting, and filtering criteria
 * @returns A query configuration object compatible with TanStack Query including:
 *  - queryKey: A unique key for caching the query results
 *  - queryFn: The async function to fetch the filtered variables
 *  - staleTime: How long the data should be considered fresh (1 second)
 *  - placeholderData: Uses previous data while loading new data
 */
export const buildFilterVariablesQuery = (options: VariablesFilter) =>
	queryOptions({
		queryKey: queryKeyFactory.listFilter(options),
		queryFn: async () => {
			const response = await getQueryService().POST("/variables/filter", {
				body: options,
			});
			return response.data ?? [];
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for counting variables with filters
 * @param options - Optional filter options for the variables count query
 * @returns A query configuration object compatible with TanStack Query including:
 *  - queryKey: A unique key for caching the count results
 *  - queryFn: The async function to fetch the filtered count
 *  - staleTime: How long the data should be considered fresh (1 second)
 *  - placeholderData: Uses previous data while loading new data
 */
export const buildFilterCountQuery = (options: VariablesFilter) =>
	queryOptions({
		queryKey: queryKeyFactory.count(options),
		queryFn: async () => {
			const response = await getQueryService().POST("/variables/count", {
				body: options,
			});
			return response.data ?? 0;
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for counting all variables
 * @returns A query configuration object compatible with TanStack Query including:
 *  - queryKey: A unique key for caching the count results
 *  - queryFn: The async function to fetch the filtered count
 *  - staleTime: How long the data should be considered fresh (1 second)
 *  - placeholderData: Uses previous data while loading new data
 */
export const buillAllCountQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.countsAll(),
		queryFn: async () => {
			const response = await getQueryService().POST("/variables/count");
			return response.data ?? 0;
		},
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

/**
 * Hook for fetching and managing variables data with filtering, pagination, and counts
 *
 * @param options - Filter options for the variables query including pagination, sorting, and filtering criteria
 * @returns An object containing:
 *  - variables: Array of filtered variables
 *  - isLoadingVariables: Loading state for variables query
 *  - isErrorVariables: Error state for variables query
 *  - errorVariables: Error object for variables query
 *  - filteredCount: Count of variables matching current filters
 *  - isLoadingFilteredCount: Loading state for filtered count
 *  - isErrorFilteredCount: Error state for filtered count
 *  - totalCount: Total count of all variables
 *  - isLoadingTotalCount: Loading state for total count
 *  - isErrorTotalCount: Error state for total count
 *  - isLoading: Overall loading state
 *  - isError: Overall error state
 *
 * @example
 * ```ts
 * const {
 *   variables,
 *   isLoading,
 *   filteredCount,
 *   totalCount
 * } = useVariables({
 *   offset: 0,
 *   limit: 10,
 *   sort: "CREATED_DESC",
 *   variables: {
 *     operator: "and_",
 *     name: { like_: "test" },
 *     tags: { operator: "and_", all_: ["prod"] }
 *   }
 * });
 * ```
 */
export const useVariables = (options: VariablesFilter) => {
	const results = useQueries({
		queries: [
			// Filtered variables with pagination
			buildFilterVariablesQuery(options),
			// Filtered count
			buildFilterCountQuery(options),
			// Total count
			buillAllCountQuery(),
		],
	});

	const [variablesQuery, filteredCountQuery, totalCountQuery] = results;

	return {
		// Variables with pagination
		variables: variablesQuery.data ?? [],
		isLoadingVariables: variablesQuery.isLoading,
		isErrorVariables: variablesQuery.isError,
		errorVariables: variablesQuery.error,

		// Filtered count
		filteredCount: filteredCountQuery.data ?? 0,
		isLoadingFilteredCount: filteredCountQuery.isLoading,
		isErrorFilteredCount: filteredCountQuery.isError,

		// Total count
		totalCount: totalCountQuery?.data ?? filteredCountQuery.data ?? 0,
		isLoadingTotalCount: totalCountQuery?.isLoading ?? false,
		isErrorTotalCount: totalCountQuery?.isError ?? false,

		// Overall loading state
		isLoading: results.some((result) => result.isLoading),
		isError: results.some((result) => result.isError),
	};
};

/**
 * Data loader for the useVariables hook, used by TanStack Router
 * Prefetches variables data, filtered count, and total count
 *
 * @param deps - Filter options to use for prefetching
 * @param context - Router context containing queryClient
 * @returns Promise that resolves when all data is prefetched
 */
useVariables.loader = ({
	deps,
	context,
}: {
	deps: VariablesFilter;
	context: { queryClient: QueryClient };
}) =>
	Promise.all([
		context.queryClient.ensureQueryData(buildFilterVariablesQuery(deps)),
		context.queryClient.ensureQueryData(buildFilterCountQuery(deps)),
		context.queryClient.ensureQueryData(buillAllCountQuery()),
	]);

/**
 * Hook for creating a new variable
 *
 * @param options - Configuration options
 * @param options.onSuccess - Callback function to run when variable is successfully created
 * @param options.onError - Callback function to run when variable creation fails
 * @returns Mutation object for creating a variable with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createVariable, isLoading } = useCreateVariable();
 *
 * // Create a new variable
 * createVariable({
 *   name: 'MY_VARIABLE',
 *   value: 'secret-value',
 *   tags: ['production', 'secrets']
 * }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Variable created successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to create variable:', error);
 *   }
 * });
 * ```
 */
export const useCreateVariable = () => {
	const queryClient = useQueryClient();

	const { mutate: createVariable, ...rest } = useMutation({
		mutationFn: (variable: components["schemas"]["VariableCreate"]) => {
			return getQueryService().POST("/variables/", {
				body: variable,
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});

	return { createVariable, ...rest };
};

type VariableUpdateWithId = components["schemas"]["VariableUpdate"] & {
	id: string;
};

/**
 * Hook for updating an existing variable
 *
 * @param options - Configuration options for the mutation
 * @param options.onSuccess - Callback function to run when update succeeds
 * @param options.onError - Callback function to run when update fails
 * @returns Mutation object for updating a variable with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { updateVariable } = useUpdateVariable();
 *
 * // Update an existing variable
 * updateVariable({
 *   id: 'existing-variable-id',
 *   name: 'UPDATED_NAME',
 *   value: 'new-value',
 *   tags: ['production']
 * }, {
 *   onSuccess: () => {
 *     // Handle successful update
 *   },
 *   onError: (error) => {
 *     console.error('Failed to update variable:', error);
 *   }
 * });
 * ```
 */
export const useUpdateVariable = () => {
	const queryClient = useQueryClient();

	const { mutate: updateVariable, ...rest } = useMutation({
		mutationFn: (variable: VariableUpdateWithId) => {
			const { id, ...body } = variable;
			return getQueryService().PATCH("/variables/{id}", {
				params: { path: { id } },
				body,
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});

	return { updateVariable, ...rest };
};

/**
 * Hook for deleting a variable
 *
 * @returns Mutation object for deleting a variable with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteVariable } = useDeleteVariable();
 *
 * // Delete a variable by ID
 * deleteVariable('variable-id-to-delete', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *   },
 *   onError: (error) => {
 *     console.error('Failed to delete variable:', error);
 *   }
 * });
 * ```
 */
export const useDeleteVariable = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteVariable, ...rest } = useMutation({
		mutationFn: async (id: string) =>
			await getQueryService().DELETE("/variables/{id}", {
				params: { path: { id } },
			}),
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});

	return { deleteVariable, ...rest };
};
