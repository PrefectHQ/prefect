import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions, useQuery } from "@tanstack/react-query";

export type GlobalConcurrencyLimit =
	components["schemas"]["GlobalConcurrencyLimitResponse"];
export type GlobalConcurrencyLimitsFilter =
	components["schemas"]["Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post"];

/**
 * ```
 *  🏗️ Variable queries construction 👷
 *  all   =>   ['global-concurrency-limits'] // key to match ['global-concurrency-limits', ...
 *  list  =>   ['global-concurrency-limits', 'list'] // key to match ['global-concurrency-limits', 'list', ...
 *             ['global-concurrency-limits', 'list', { ...filter1 }]
 *             ['global-concurrency-limits', 'list', { ...filter2 }]
 *  details => ['global-concurrency-limits', 'details'] // key to match ['global-concurrency-limits', 'details', ...]
 *             ['global-concurrency-limits', 'details', { ...globalConcurrencyLimit1 }]
 *             ['global-concurrency-limits', 'details', { ...globalConcurrencyLimit2 }]
 * ```
 * */
const queryKeyFactory = {
	all: () => ["global-concurrency-limits"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: GlobalConcurrencyLimitsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id_or_name: string) =>
		[...queryKeyFactory.details(), id_or_name] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListGlobalConcurrencyLimitsQuery = (
	filter: GlobalConcurrencyLimitsFilter,
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST(
				"/v2/concurrency_limits/filter",
				{ body: filter },
			);
			return res.data ?? [];
		},
	});

export const buildGetGlobalConcurrencyLimitQuery = (id_or_name: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id_or_name),
		queryFn: async () => {
			const res = await getQueryService().GET(
				"/v2/concurrency_limits/{id_or_name}",
				{ params: { path: { id_or_name } } },
			);
			return res.data ?? null;
		},
	});

/**
 *
 * @param filter
 * @returns list of global concurrency limits as a QueryResult object
 */
export const useListGlobalConcurrencyLimits = (
	filter: GlobalConcurrencyLimitsFilter,
) => useQuery(buildListGlobalConcurrencyLimitsQuery(filter));

/**
 *
 * @param id_or_name
 * @returns details about the specified global concurrency limit as a QueryResult object
 */
export const useGetGlobalConcurrencyLimit = (id_or_name: string) =>
	useQuery(buildGetGlobalConcurrencyLimitQuery(id_or_name));

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

// TODO:
