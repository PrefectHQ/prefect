import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	keepPreviousData,
	type QueryClient,
	useQueries,
} from "@tanstack/react-query";

type QueryKeys = {
	all: readonly ["deployments"];
	filtered: (
		options?: UseDeploymentsOptions,
	) => readonly ["deployments", "filtered", string];
	filteredCount: (
		options?: UseDeploymentsOptions,
	) => readonly ["deployments", "filtered-count", string];
};

const queryKeys: QueryKeys = {
	all: ["deployments"],
	filtered: (options?: UseDeploymentsOptions) => [
		...queryKeys.all,
		"filtered",
		JSON.stringify(options),
	],
	filteredCount: (options?: UseDeploymentsOptions) => [
		...queryKeys.all,
		"filtered-count",
		JSON.stringify(options),
	],
};

const buildDeploymentsQuery = (options?: UseDeploymentsOptions) => ({
	queryKey: queryKeys.filtered(options),
	queryFn: async () => {
		const response = await getQueryService().POST("/deployments/filter", {
			body: options,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

const buildCountQuery = (options?: UseDeploymentsOptions) => ({
	queryKey: queryKeys.filteredCount(options),
	queryFn: async () => {
		const response = await getQueryService().POST("/deployments/count", {
			body: options,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

type UseDeploymentsOptions =
	components["schemas"]["Body_read_deployments_deployments_filter_post"];

export const useDeployments = (options?: UseDeploymentsOptions) => {
	const results = useQueries({
		queries: [
			buildDeploymentsQuery(options),
			buildCountQuery(options),
			buildCountQuery(),
		],
	});

	const [deploymentsQuery, filteredCountQuery, totalCountQuery] = results;

	return {
		// Deployments with pagination
		deployments: deploymentsQuery.data ?? [],
		isLoadingDeployments: deploymentsQuery.isLoading,
		isErrorDeployments: deploymentsQuery.isError,
		errorDeployments: deploymentsQuery.error,

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
 * Data loader for the useDeployments hook, used by TanStack Router
 * Prefetches deployments data, filtered count, and total count
 */
useDeployments.loader = ({
	deps,
	context,
}: {
	deps: UseDeploymentsOptions;
	context: { queryClient: QueryClient };
}) =>
	Promise.all([
		context.queryClient.ensureQueryData(buildDeploymentsQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery(deps)),
		context.queryClient.ensureQueryData(buildCountQuery()),
	]);
