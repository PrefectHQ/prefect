import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";

export type BlockDocument = components["schemas"]["BlockDocument"];
export type BlockDocumentsFilter =
	components["schemas"]["Body_read_block_documents_block_documents_filter_post"];

/**
 * ```
 *  🏗️ Block documents queries construction 👷
 *  all			=>   ['"block-documents'] // key to match ['"block-documents', ...
 *  lists		=>   ['"block-documents', 'list'] // key to match ['"block-documents, 'list', ...
 *  listFilters	=>   ['"block-documents', 'list', 'filter']
 *  listFilter	=>   ['"block-documents', 'list', 'filter', { ...filter1 }]
 *  counts		=>   ['"block-documents', 'count'] // key to match ['"block-documents, 'list', ...
 *  countAll	=>   ['"block-documents', 'count', 'all']
 *  countFilter	=>   ['"block-documents', 'count', { ...filter1 }]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["block-documents"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	listFilters: () => [...queryKeyFactory.lists(), "filter"] as const,
	listFilter: (filter: BlockDocumentsFilter) =>
		[...queryKeyFactory.listFilters(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "count"] as const,
	countAll: () => [...queryKeyFactory.counts(), "all"] as const,
	countFilter: (filter: BlockDocumentsFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListFilterBlockDocumentsQuery = (
	filter: BlockDocumentsFilter = {
		offset: 0,
		sort: "BLOCK_TYPE_AND_NAME_ASC",
		include_secrets: false,
	},
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.listFilter(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_documents/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' exoected");
			}
			return res.data;
		},
		enabled,
	});

export const buildCountFilterBlockDocumentsQuery = (
	filter: BlockDocumentsFilter = {
		offset: 0,
		sort: "BLOCK_TYPE_AND_NAME_ASC",
		include_secrets: false,
	},
) =>
	queryOptions({
		queryKey: queryKeyFactory.countFilter(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_documents/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
	});
export const buildCountAllBlockDocumentsQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.countAll(),
		queryFn: async () => {
			const res = await getQueryService().POST("/block_documents/count");
			return res.data ?? 0;
		},
	});

// ----------------------------
// --------  Mutations --------
// ----------------------------

/**
 * Hook for deleting a block document
 *
 * @returns Mutation object for deleting a block document with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteBlockDocument } = useDeleteBlockDocument();
 *
 * // Delete a block document by id
 * deleteBlockDocument('block-document-id', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *     console.log('Block document deleted successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to delete block document:', error);
 *   }
 * });
 * ```
 */
export const useDeleteBlockDocument = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteBlockDocument, ...rest } = useMutation({
		mutationFn: (id: string) =>
			getQueryService().DELETE("/block_documents/{id}", {
				params: { path: { id } },
			}),
		onSettled: () => {
			return Promise.all([
				queryClient.invalidateQueries({
					queryKey: queryKeyFactory.lists(),
				}),
				queryClient.invalidateQueries({
					queryKey: queryKeyFactory.counts(),
				}),
			]);
		},
	});

	return { deleteBlockDocument, ...rest };
};
