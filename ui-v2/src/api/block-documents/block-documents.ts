import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions } from "@tanstack/react-query";

export type BlockDocument = components["schemas"]["BlockDocument"];
export type BlockDocumentsFilter =
	components["schemas"]["Body_read_block_documents_block_documents_filter_post"];

/**
 * ```
 *  🏗️ Block documents queries construction 👷
 *  all   =>   ['"block-documents'] // key to match ['"block-documents', ...
 *  list  =>   ['"block-documents', 'list'] // key to match ['"block-documents, 'list', ...
 *             ['"block-documents', 'list', { ...filter1 }]
 *             ['"block-documents', 'list', { ...filter2 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["block-documents"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: BlockDocumentsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildFilterBlockDocumentsQuery = (
	filter: BlockDocumentsFilter = {
		offset: 0,
		sort: "BLOCK_TYPE_AND_NAME_ASC",
		include_secrets: false,
	},
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_documents/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		enabled,
	});
