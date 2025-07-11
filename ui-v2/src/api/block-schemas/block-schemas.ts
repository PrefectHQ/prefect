import { queryOptions } from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type BlockSchema = components["schemas"]["BlockSchema"];
export type BlockSchemaFilter =
	components["schemas"]["Body_read_block_schemas_block_schemas_filter_post"];

/**
 * ```
 *  🏗️ Block Schema queries construction 👷
 *  all			=>   ['block-schemas'] // key to match ['block-schemas', ...
 *  lists		=>   ['block-schemas', 'list'] // key to match ['block-types, 'list', ...
 *  listFilters	=>   ['block-schemas', 'list', 'filter']
 *  listFilter	=>   ['block-schemas', 'list', 'filter', { ...filter1 }]
 *  details		=>   ['block-schemas', 'detail']
 *  detail		=>   ['block-schemas', id]


 * ```
 * */
export const queryKeyFactory = {
	all: () => ["block-schemas"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	listFilters: () => [...queryKeyFactory.lists(), "filter"] as const,
	listFilter: (filter: BlockSchemaFilter) =>
		[...queryKeyFactory.lists(), "filter", filter] as const,
	details: () => [...queryKeyFactory.all(), "detail"] as const,
	detail: (slug: string) => [...queryKeyFactory.details(), slug] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------

export const buildListFilterBlockSchemasQuery = (
	filter: BlockSchemaFilter = { offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.listFilter(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_schemas/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
	});

export const buildGetBlockSchemaQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/block_schemas/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
