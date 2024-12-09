import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
  QueryClient,
  queryOptions,
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query";

export type BlockDocument = components["schemas"]["BlockDocument"];
export type BlockDocumentsFilter = components["schemas"]["Body_read_block_documents_block_documents_filter_post"]

/**
 * ```
 *  🏗️ Block documents queries construction 👷
 *  all   =>   ['block-documents'] // key to match ['block-documents', ...
 *  list  =>   ['block-documents', 'list'] // key to match ['block-documents', 'list', ...
 *             ['block-documents', 'list', { ...filter1 }]
 *             ['block-documents', 'list', { ...filter2 }]
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
export const buildListBlockDocumentsQuery = (
  filter: BlockDocumentsFilter = { 
    block_documents: { operator: "and_", is_anonymous: { eq_: false } },
    include_secrets: false,
    sort: null,
    offset: 0,
    limit: undefined
  }
) =>
  queryOptions({
    queryKey: queryKeyFactory.list(filter),
    queryFn: async () => {
      const res = await getQueryService().POST("/block_documents/filter", {
        body: { 
          block_documents: filter.block_documents,
          include_secrets: false,
          sort: filter.sort ?? null,
          offset: filter.offset ?? 0,
          limit: filter.limit ?? undefined
        },
      });
      return res.data ?? [];
    },
  });

/**
 *
 * @param filter
 * @returns list of block documents as a SuspenseQueryResult object
 */
export const useListBlockDocuments = (
  filter: BlockDocumentsFilter = { 
    block_documents: { operator: "and_", is_anonymous: { eq_: false } },
    include_secrets: false,
    sort: null,
    offset: 0,
    limit: undefined
  }
) => useSuspenseQuery(buildListBlockDocumentsQuery(filter));

useListBlockDocuments.loader = ({
  context,
}: {
  context: { queryClient: QueryClient };
}) => context.queryClient.ensureQueryData(buildListBlockDocumentsQuery());

// ----- ✍🏼 Mutations 🗄️
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
 * deleteBlockDocument('id-to-delete', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *   },
 *   onError: (error) => {
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
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: queryKeyFactory.lists(),
      });
    },
  });
  return {
    deleteBlockDocument,
    ...rest,
  };
};

/**
 * Hook for creating a new block document
 *
 * @returns Mutation object for creating a block document with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createBlockDocument } = useCreateBlockDocument();
 *
 * // Create a new block document
 * createBlockDocument({
 *   name: "my-block",
 *   data: { ... },
 * }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *   },
 *   onError: (error) => {
 *     console.error('Failed to create block document:', error);
 *   }
 * });
 * ```
 */
export const useCreateBlockDocument = () => {
  const queryClient = useQueryClient();
  const { mutate: createBlockDocument, ...rest } = useMutation({
    mutationFn: (body: components["schemas"]["BlockDocumentCreate"]) =>
      getQueryService().POST("/block_documents/", {
        body,
      }),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: queryKeyFactory.lists(),
      });
    },
  });
  return {
    createBlockDocument,
    ...rest,
  };
};

type BlockDocumentUpdateWithId = components["schemas"]["BlockDocumentUpdate"] & {
  id: string;
};

/**
 * Hook for updating an existing block document
 *
 * @returns Mutation object for updating a block document with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { updateBlockDocument } = useUpdateBlockDocument();
 *
 * // Update an existing block document
 * updateBlockDocument({
 *   id: "1",
 *   data: { ... },
 * }, {
 *   onSuccess: () => {
 *     // Handle successful update
 *   },
 *   onError: (error) => {
 *     console.error('Failed to update block document:', error);
 *   }
 * });
 * ```
 */
export const useUpdateBlockDocument = () => {
  const queryClient = useQueryClient();
  const { mutate: updateBlockDocument, ...rest } = useMutation({
    mutationFn: ({ id, ...body }: BlockDocumentUpdateWithId) =>
      getQueryService().PATCH("/block_documents/{id}", {
        body,
        params: { path: { id } },
      }),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: queryKeyFactory.lists(),
      });
    },
  });
  return {
    updateBlockDocument,
    ...rest,
  };
};
