import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type Variable = components["schemas"]["Variable"];
export type VariablesFilter =
	components["schemas"]["Body_read_variables_variables_filter_post"];

/**
 * Query key factory for variables-related queries
 *
 * @property {function} all - Returns base key for all variable queries
 * @property {function} lists - Returns key for all list-type variable queries
 * @property {function} list - Generates key for specific filtered variable queries
 * @property {function} counts - Returns key for all count-type variable queries
 * @property {function} count - Generates key for specific filtered count queries
 *
 * ```
 * all				=>   ['variables']
 * lists			=>   ['variables', 'list']
 * lists-filter		=>   ['variables', 'list', 'filter']
 * list-filter		=>   ['variables', 'list', 'filter', { ...filter }]
 * counts			=>   ['variables', 'counts']
 * count			=>   ['variables', 'counts', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["variables"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	"lists-filter": () => [...queryKeyFactory.lists(), "filter"] as const,
	"list-filter": (filter: VariablesFilter) =>
		[...queryKeyFactory["lists-filter"](), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (filter?: VariablesFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching filtered variables
 *
 * @param filter - Filter options for the variables query including:
 *   - offset: Number of items to skip (default: 0)
 *   - limit: Number of items per page (default: 10)
 *   - sort: Sort order for results (default: "CREATED_DESC")
 *   - variables: Optional variable-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildFilterVariablesQuery({
 *   offset: 0,
 *   limit: 25,
 *   sort: "NAME_ASC"
 * });
 * ```
 */
export const buildFilterVariablesQuery = (
	filter: VariablesFilter = {
		offset: 0,
		limit: 10,
		sort: "CREATED_DESC",
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory["list-filter"](filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/variables/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for counting variables based on filter criteria
 *
 * @param filter - Optional filter options for the variables count query
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * // Count all variables
 * const query = buildCountVariablesQuery();
 *
 * // Count filtered variables
 * const query = buildCountVariablesQuery({
 *   variables: {
 *     operator: "and_",
 *     name: { like_: "my-variable" }
 *   }
 * });
 * ```
 */
export const buildCountVariablesQuery = (filter?: VariablesFilter) =>
	queryOptions({
		queryKey: queryKeyFactory.count(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/variables/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
		placeholderData: keepPreviousData,
	});

// ----------------------------
// --------  Mutations --------
// ----------------------------

/**
 * Hook for creating a new variable
 *
 * @returns Mutation object for creating a variable with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createVariable, isPending } = useCreateVariable();
 *
 * createVariable({
 *   name: 'MY_VARIABLE',
 *   value: 'secret-value',
 *   tags: ['production', 'secrets']
 * }, {
 *   onSuccess: () => {
 *     console.log('Variable created successfully');
 *   },
 *   onError: (error) => {
 *     console.error('Failed to create variable:', error);
 *   }
 * });
 * ```
 */
export const useCreateVariable = () => {
	const queryClient = useQueryClient();

	const { mutate: createVariable, ...rest } = useMutation({
		mutationFn: async (variable: components["schemas"]["VariableCreate"]) => {
			return (await getQueryService()).POST("/variables/", {
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
 * @returns Mutation object for updating a variable with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { updateVariable } = useUpdateVariable();
 *
 * updateVariable({
 *   id: 'existing-variable-id',
 *   name: 'UPDATED_NAME',
 *   value: 'new-value',
 *   tags: ['production']
 * }, {
 *   onSuccess: () => {
 *     console.log('Variable updated successfully');
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
		mutationFn: async (variable: VariableUpdateWithId) => {
			const { id, ...body } = variable;
			return (await getQueryService()).PATCH("/variables/{id}", {
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
 * deleteVariable('variable-id-to-delete', {
 *   onSuccess: () => {
 *     console.log('Variable deleted successfully');
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
			await (await getQueryService()).DELETE("/variables/{id}", {
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
