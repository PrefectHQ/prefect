import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQueryClient,
	useQueries,
	keepPreviousData,
	type QueryClient,
} from "@tanstack/react-query";

type UseVariablesOptions =
	components["schemas"]["Body_read_variables_variables_filter_post"];
type VariableUpdateWithId = components["schemas"]["VariableUpdate"] & {
	id: string;
};
type VariablesFilter = components["schemas"]["VariableFilter"];

// ----- 🔑 Queries 🗄️
// ----------------------------

/**
 * ```
 *  🏗️ Variable queries construction 👷
 *  all   =>   ['variables'] // key to match ['variables', ..., ...]
 *  list  =>   ['variables', 'list'] // key to match ['variables', 'list', ..., ...]
 *             ['variables', 'list', { ...withOptionsFoo }]
 *             ['variables', 'list', { ...withOptionsBar }]
 *             ['variables', 'list', { ...withOptionsBaz }]
 *  count =>   ['variables', 'count'] // key to match ['variables', 'count', ..., ...]
 *             ['variables', 'count', {}] // all count
 *             ['variables', 'count', { ...withOptionsFoo }]
 *             ['variables', 'count', { ...withOptionsBar }]
 *             ['variables', 'count', { ...withOptionsBaz }]
 * ```
 */
const variableQueries = {
	all: () => ["variables"] as const,
	lists: () => [...variableQueries.all(), "list"] as const,
	list: (options: UseVariablesOptions) =>
		queryOptions({
			queryKey: [...variableQueries.lists(), options] as const,
			queryFn: async () => {
				const response = await getQueryService().POST("/variables/filter", {
					body: options,
				});
				return response.data;
			},
			staleTime: 1000,
			placeholderData: keepPreviousData,
		}),
	counts: () => [...variableQueries.all(), "count"] as const,
	count: (variables?: VariablesFilter | null) => {
		const body = { variables };
		return queryOptions({
			queryKey: [...variableQueries.counts(), body] as const,
			queryFn:
				() => async (body: UseVariablesOptions | Record<never, never>) => {
					const response = await getQueryService().POST("/variables/count", {
						body,
					});
					return response.data;
				},
			staleTime: 1000,
			placeholderData: keepPreviousData,
		});
	},
} as const;

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
export const useVariables = (options: UseVariablesOptions) => {
	const results = useQueries({
		queries: [
			// Filtered variables with pagination
			variableQueries.list(options),
			// Filtered count
			variableQueries.count(options.variables),
			// Total count
			variableQueries.count(),
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
	deps: UseVariablesOptions;
	context: { queryClient: QueryClient };
}) =>
	Promise.all([
		context.queryClient.ensureQueryData(variableQueries.list(deps)),
		context.queryClient.ensureQueryData(variableQueries.count(deps.variables)),
		context.queryClient.ensureQueryData(variableQueries.count()),
	]);

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

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
				queryKey: variableQueries.all(),
			});
		},
	});

	return { createVariable, ...rest };
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
				queryKey: variableQueries.all(),
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
		mutationFn: (id: string) => {
			return getQueryService().DELETE("/variables/{id}", {
				params: { path: { id } },
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: variableQueries.all(),
			});
		},
	});

	return { deleteVariable, ...rest };
};
