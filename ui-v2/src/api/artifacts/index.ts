import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import type { components } from "../prefect";
import { getQueryService } from "../service";

export type Artifact = components["schemas"]["Artifact"];
export type ArtifactWithFlowRunAndTaskRun = Artifact & {
	flow_run?: components["schemas"]["FlowRun"];
	task_run?: components["schemas"]["TaskRun"];
};

export type ArtifactsFilter =
	components["schemas"]["Body_read_artifacts_artifacts_filter_post"];

/**
 * Query key factory for artifacts-related queries
 *
 * @property {function} all - Returns base key for all artifacts queries
 * @property {function} lists - Returns key for all list-type artifact queries
 * @property {function} list - Generates key for specific filtered artifact queries
 * @property {function} counts - Returns key for all count-type artifact queries
 * @property {function} count - Generates key for specific filtered count queries
 *
 * ```
 * all				=>   ['artifacts']
 * lists			=>   ['artifacts', 'list']
 * lists-filter		=>   ['artifacts', 'list', 'filter']
 * list-filter		=>   ['artifacts', 'list', 'filter', { ...filter }]
 * counts			=>   ['artifacts', 'counts']
 * count			=>   ['artifacts', 'counts', { ...filter }]
 * details          =>   ['artifacts', 'details']
 * detail           =>   ['artifacts', 'details', id]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["artifacts"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	"lists-filter": () => [...queryKeyFactory.lists(), "filter"] as const,
	"list-filter": (filter: ArtifactsFilter) =>
		[...queryKeyFactory["lists-filter"](), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (filter: ArtifactsFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching paginated artifacts
 *
 * @param filter - Pagination and filter options including:
 * - offset: number
 * - sort: string
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buidFilterArtifactsQuery({
 *   offset: 0,
 *   sort: "ID_DESC",
 * });
 * ```
 */
export const buildListArtifactsQuery = (
	filter: ArtifactsFilter = {
		offset: 0,
		sort: "ID_DESC",
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory["list-filter"](filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/artifacts/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for fetching counts of artifacts
 *
 * @param filter - Filter options for artifacts
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildCountArtifactsQuery({
 *  offset: 0,
 * sort: "ID_DESC",
 * });
 * ```
 */
export const buildCountArtifactsQuery = (
	filter: ArtifactsFilter = {
		offset: 0,
		sort: "ID_DESC",
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory.count(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/artifacts/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
		placeholderData: 0,
	});

/**
 * Builds a query configuration for fetching a single artifact by ID
 *
 * @param id - ID of the artifact to fetch
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = buildGetArtifactQuery("123");
 * ```
 * */
export const buildGetArtifactQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/artifacts/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
