import { queryOptions } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";

/**
 * Query key factory for workers-related queries
 */
export const queryKeyFactory = {
	all: () => ["workers"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: () => [...queryKeyFactory.lists(), "collection"] as const,
};

/**
 * Builds a query configuration for fetching the worker collection
 *
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useSuspenseQuery(buildListWorkersQuery());
 * ```
 */
export const buildListWorkersQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.list(),
		queryFn: async () => {
			const res = await getQueryService().GET("/collections/views/{view}", {
				params: { path: { view: "aggregate-worker-metadata" } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
