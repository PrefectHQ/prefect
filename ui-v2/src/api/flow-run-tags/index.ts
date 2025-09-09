import { queryOptions } from "@tanstack/react-query";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";

/**
 * Query key factory for flow run tags queries
 */
export const queryKeyFactory = {
	all: () => ["flowRunTags"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
};

/**
 * Builds a query configuration for fetching available flow run tags
 *
 * This function fetches recent flow runs and aggregates their unique tags
 * to provide autocomplete options for tag filtering.
 *
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: tags = [] } = useSuspenseQuery(buildListFlowRunTagsQuery());
 * ```
 */
export const buildListFlowRunTagsQuery = () => {
	return queryOptions({
		queryKey: queryKeyFactory.lists(),
		queryFn: async (): Promise<string[]> => {
			// Fetch recent flow runs to get available tags
			const flowRunsQuery = buildFilterFlowRunsQuery({
				limit: 1000, // Get a good sample of recent flow runs
				sort: "CREATED_DESC",
				offset: 0,
			});

			const flowRuns = await flowRunsQuery.queryFn();

			// Extract and deduplicate tags from flow runs
			const tagSet = new Set<string>();

			flowRuns.forEach((flowRun) => {
				if (flowRun.tags && Array.isArray(flowRun.tags)) {
					flowRun.tags.forEach((tag) => {
						if (typeof tag === "string" && tag.trim()) {
							tagSet.add(tag.trim());
						}
					});
				}
			});

			// Return sorted unique tags
			return Array.from(tagSet).sort((a, b) =>
				a.toLowerCase().localeCompare(b.toLowerCase()),
			);
		},
		staleTime: 5 * 60 * 1000, // Cache for 5 minutes
		gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
	});
};
