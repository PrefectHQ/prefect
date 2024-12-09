import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
  QueryClient,
  queryOptions,
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query";

export type BlockType = components["schemas"]["BlockType"];
export type BlockTypesFilter = components["schemas"]["Body_read_block_types_block_types_filter_post"]

/**
 * ```
 *  🏗️ Block types queries construction 👷
 *  all   =>   ['block-types'] // key to match ['block-types', ...
 *  list  =>   ['block-types', 'list'] // key to match ['block-types', 'list', ...
 *             ['block-types', 'list', { ...filter1 }]
 *             ['block-types', 'list', { ...filter2 }]
 * ```
 * */
export const queryKeyFactory = {
  all: () => ["block-types"] as const,
  lists: () => [...queryKeyFactory.all(), "list"] as const,
  list: (filter: BlockTypesFilter) =>
    [...queryKeyFactory.lists(), filter] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListBlockTypesQuery = (
  filter: BlockTypesFilter = { 
    block_types: { name: null, slug: null },
    offset: 0,
    limit: undefined
  }
) =>
  queryOptions({
    queryKey: queryKeyFactory.list(filter),
    queryFn: async () => {
      const res = await getQueryService().POST("/block_types/filter", {
        body: { 
          block_types: filter.block_types,
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
 * @returns list of block types as a SuspenseQueryResult object
 */
export const useListBlockTypes = (
  filter: BlockTypesFilter = { 
    block_types: { name: null, slug: null },
    offset: 0,
    limit: undefined
  }
) => useSuspenseQuery(buildListBlockTypesQuery(filter));

useListBlockTypes.loader = ({
  context,
}: {
  context: { queryClient: QueryClient };
}) => context.queryClient.ensureQueryData(buildListBlockTypesQuery());

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

/**
 * Hook for creating a new block type
 *
 * @returns Mutation object for creating a block type with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createBlockType } = useCreateBlockType();
 *
 * // Create a new block type
 * createBlockType({
 *   name: "my-block-type",
 *   slug: "my-block-type",
 *   logo_url: "https://...",
 * }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *   },
 *   onError: (error) => {
 *     console.error('Failed to create block type:', error);
 *   }
 * });
 * ```
 */
export const useCreateBlockType = () => {
  const queryClient = useQueryClient();
  const { mutate: createBlockType, ...rest } = useMutation({
    mutationFn: (body: components["schemas"]["BlockTypeCreate"]) =>
      getQueryService().POST("/block_types/", {
        body,
      }),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: queryKeyFactory.lists(),
      });
    },
  });
  return {
    createBlockType,
    ...rest,
  };
};

type BlockTypeUpdateWithId = components["schemas"]["BlockTypeUpdate"] & {
  id: string;
};

/**
 * Hook for updating an existing block type
 *
 * @returns Mutation object for updating a block type with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { updateBlockType } = useUpdateBlockType();
 *
 * // Update an existing block type
 * updateBlockType({
 *   id: "1",
 *   logo_url: "https://...",
 * }, {
 *   onSuccess: () => {
 *     // Handle successful update
 *   },
 *   onError: (error) => {
 *     console.error('Failed to update block type:', error);
 *   }
 * });
 * ```
 */
export const useUpdateBlockType = () => {
  const queryClient = useQueryClient();
  const { mutate: updateBlockType, ...rest } = useMutation({
    mutationFn: ({ id, ...body }: BlockTypeUpdateWithId) =>
      getQueryService().PATCH("/block_types/{id}", {
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
    updateBlockType,
    ...rest,
  };
};
