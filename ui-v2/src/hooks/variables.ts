import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useToast } from "@/hooks/use-toast";
import {
	useMutation,
	useQueryClient,
	useQueries,
	keepPreviousData,
	type QueryClient,
} from "@tanstack/react-query";

type UseVariablesOptions =
	components["schemas"]["Body_read_variables_variables_filter_post"];

type VariableKeys = {
	all: readonly ["variables"];
	filtered: (
		options: UseVariablesOptions,
	) => readonly ["variables", "filtered", string];
	filteredCount: (options?: UseVariablesOptions) => readonly string[];
	total: readonly ["variables", "total"];
};

const queryKeys: VariableKeys = {
	all: ["variables"],
	filtered: (options) => [
		...queryKeys.all,
		"filtered",
		JSON.stringify(options),
	],
	filteredCount: (options) => {
		const key = [...queryKeys.all, "filtered-count"];
		if (options?.variables?.name?.like_) key.push(options.variables.name.like_);
		if (options?.variables?.tags?.all_?.length)
			key.push(JSON.stringify(options.variables.tags));
		return key;
	},
	total: ["variables", "total"],
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
const buildVariablesQuery = (options: UseVariablesOptions) => ({
	queryKey: queryKeys.filtered(options),
	queryFn: async () => {
		const response = await getQueryService().POST("/variables/filter", {
			body: options,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

/**
 * Builds a query configuration for counting variables with optional filters
 * @param options - Optional filter options for the variables count query
 * @returns A query configuration object compatible with TanStack Query including:
 *  - queryKey: A unique key for caching the count results
 *  - queryFn: The async function to fetch the filtered count
 *  - staleTime: How long the data should be considered fresh (1 second)
 *  - placeholderData: Uses previous data while loading new data
 */
const buildCountQuery = (options?: UseVariablesOptions) => ({
	queryKey: queryKeys.filteredCount(options),
	queryFn: async () => {
		const body = options?.variables ? { variables: options.variables } : {};
		const response = await getQueryService().POST("/variables/count", {
			body,
		});
		return response.data;
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
 */
export const useVariables = (options: UseVariablesOptions) => {
	const results = useQueries({
		queries: [
			// Filtered variables with pagination
			buildVariablesQuery(options),
			// Filtered count
			buildCountQuery(options),
			// Total count
			buildCountQuery(),
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
		context.queryClient.ensureQueryData(buildVariablesQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery()),
	]);

type UseCreateVariableOptions = {
	onSuccess: () => void;
	onError: (error: Error) => void;
};

export const useCreateVariable = ({
	onSuccess,
	onError,
}: UseCreateVariableOptions) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: components["schemas"]["VariableCreate"]) => {
			return getQueryService().POST("/variables/", {
				body: variable,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === queryKeys.all,
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable created",
			});
			onSuccess();
		},
		onError,
	});
};

type UseUpdateVariableProps = {
	onSuccess: () => void;
	onError: (error: Error) => void;
};

type VariableUpdateWithId = components["schemas"]["VariableUpdate"] & {
	id: string;
};

export const useUpdateVariable = ({
	onSuccess,
	onError,
}: UseUpdateVariableProps) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: VariableUpdateWithId) => {
			const { id, ...body } = variable;
			return getQueryService().PATCH("/variables/{id}", {
				params: { path: { id } },
				body,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === queryKeys.all,
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable updated",
			});
			onSuccess();
		},
		onError,
	});
};
