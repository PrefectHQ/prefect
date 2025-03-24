import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions } from "@tanstack/react-query";

export type BlockType = components["schemas"]["BlockType"];
export type BlockTypesFilter =
	components["schemas"]["Body_read_block_types_block_types_filter_post"];
/**
 * ```
 *  🏗️ Block Types queries construction 👷
 *  all			=>   ['"block-types'] // key to match ['"block-types', ...
 *  lists		=>   ['"block-types', 'list'] // key to match ['"block-types, 'list', ...
 *  listFilters	=>   ['"block-types', 'list', 'filter']
 *  listFilter	=>   ['"block-types', 'list', 'filter', { ...filter1 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["block-types"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	listFilters: () => [...queryKeyFactory.lists(), "filter"] as const,
	listFilter: (filter: BlockTypesFilter) =>
		[...queryKeyFactory.listFilters(), filter] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListFilterBlockTypesQuery = (
	filter: BlockTypesFilter = { offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.listFilter(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_types/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' exoected");
			}
			return res.data;
		},
	});
