import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions } from "@tanstack/react-query";

export type Block = components["schemas"]["BlockDocument"];
export type BlocksFilter =
	components["schemas"]["Body_read_block_documents_block_documents_filter_post"];

/**
 * ```
 *  🏗️ Blocks queries construction 👷
 *  all   =>   ['blocks'] // key to match ['blocks', ...
 *  list  =>   ['blocks', 'list'] // key to match ['blocks, 'list', ...
 *             ['blocks', 'list', { ...filter1 }]
 *             ['blocks', 'list', { ...filter2 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["blocks"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: BlocksFilter) => [...queryKeyFactory.lists(), filter] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildFilterBlocksQuery = (
	filter: BlocksFilter = {
		offset: 0,
		sort: "BLOCK_TYPE_AND_NAME_ASC",
		include_secrets: false,
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_documents/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
	});
