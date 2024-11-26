import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	keepPreviousData,
	type QueryClient,
	useQueries,
} from "@tanstack/react-query";

type QueryKeys = {
	all: readonly ["flows"];
	filtered: (
		options?: UseFlowsOptions,
	) => readonly ["flows", "filtered", string];
	filteredCount: (
		options?: UseFlowsOptions,
	) => readonly ["flows", "filtered-count", string];
};

const queryKeys: QueryKeys = {
	all: ["flows"],
	filtered: (options?: UseFlowsOptions) => [
		...queryKeys.all,
		"filtered",
		JSON.stringify(options),
	],
	filteredCount: (options?: UseFlowsOptions) => [
		...queryKeys.all,
		"filtered-count",
		JSON.stringify(options),
	],
};

const buildFlowsQuery = (options?: UseFlowsOptions) => ({
	queryKey: queryKeys.filtered(options),
	queryFn: async () => {
		const response = await getQueryService().POST("/flows/filter", {
			body: options,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

const buildCountQuery = (options?: UseFlowsOptions) => ({
	queryKey: queryKeys.filteredCount(options),
	queryFn: async () => {
		const response = await getQueryService().POST("/flows/count", {
			body: options,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

type UseFlowsOptions =
	components["schemas"]["Body_read_flows_flows_filter_post"];

export const useFlows = (options?: UseFlowsOptions, enabled = true) => {
	const results = useQueries({
		queries: [
			{
				...buildFlowsQuery(options),
				enabled,
			},
			{
				...buildCountQuery(options),
				enabled,
			},
			{ ...buildCountQuery(), enabled },
		],
	});

	const [flowsQuery, filteredCountQuery, totalCountQuery] = results;

	return {
		// Flows with pagination
		flows: flowsQuery.data ?? [],
		isLoadingFlows: flowsQuery.isLoading,
		isErrorFlows: flowsQuery.isError,
		errorFlows: flowsQuery.error,

		// Filtered count
		filteredCount: filteredCountQuery.data ?? 0,
		isLoadingFilteredCount: filteredCountQuery.isLoading,
		isErrorFilteredCount: filteredCountQuery.isError,
		errorFilteredCount: filteredCountQuery.error,

		// Total count
		totalCount: totalCountQuery.data ?? filteredCountQuery.data ?? 0,
		isLoadingTotalCount: totalCountQuery.isLoading,
		isErrorTotalCount: totalCountQuery.isError,
		errorTotalCount: totalCountQuery.error,

		// Overall loading state
		isLoading: results.some((result) => result.isLoading),
		isError: results.some((result) => result.isError),
	};
};

/**
 * Data loader for the useFlows hook, used by TanStack Router
 * Prefetches flows data, filtered count, and total count
 */
useFlows.loader = ({
	deps,
	context,
}: {
	deps: UseFlowsOptions;
	context: { queryClient: QueryClient };
}) =>
	Promise.all([
		context.queryClient.ensureQueryData(buildFlowsQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery()),
	]);
