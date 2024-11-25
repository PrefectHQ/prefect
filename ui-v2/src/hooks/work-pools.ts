import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useToast } from "@/hooks/use-toast";
import { startsWith } from "@/lib/utils";
import {
  useMutation,
  useQueryClient,
  useQueries,
  keepPreviousData,
  type QueryClient,
} from "@tanstack/react-query";

type UseWorkPoolsOptions = components["schemas"]["Body_read_work_pools_work_pools_filter_post"];

type WorkPoolKeys = {
  all: readonly ["work-pools"];
  filtered: (options: UseWorkPoolsOptions) => readonly ["work-pools", "filtered", string];
  filteredCount: (options?: UseWorkPoolsOptions) => readonly string[];
};

const workPoolKeys: WorkPoolKeys = {
  all: ["work-pools"],
  filtered: (options) => [...workPoolKeys.all, "filtered", JSON.stringify(options)],
  filteredCount: (options) => [...workPoolKeys.all, "filtered-count", JSON.stringify(options)]
}

const buildWorkPoolsQuery = (options: UseWorkPoolsOptions) => ({
  queryKey: workPoolKeys.filtered(options),
  queryFn: async () => {
    const response = await getQueryService().POST("/work_pools/filter", {
      body: options,
    });
    return response.data;
  },
  staleTime: 1000,
  placeholderData: keepPreviousData,
});

const buildCountQuery = (options?: UseWorkPoolsOptions) => ({
  queryKey: workPoolKeys.filteredCount(options),
  queryFn: async () => {
    const response = await getQueryService().POST("/work_pools/count", {
      body: options,
    });
    return response.data;
  },
  staleTime: 1000,
  placeholderData: keepPreviousData,
});

/**
 * Hook for fetching and managing work pools data with filtering, pagination, and counts
 *
 * @param options - Filter options for the work pools query including pagination, sorting, and filtering criteria
 * @returns An object containing work pools data, counts, and loading states
 *
 * @example
 * ```ts
 * const {
 *   workPools,
 *   isLoading,
 *   filteredCount,
 *   totalCount
 * } = useWorkPools({
 *   offset: 0,
 *   limit: 10,
 *   sort: "CREATED_DESC",
 *   name: "test",
 *   type: "process"
 * });
 * ```
 */
export const useWorkPools = (options: UseWorkPoolsOptions) => {
  const results = useQueries({
    queries: [
      buildWorkPoolsQuery(options),
      buildCountQuery(options),
      buildCountQuery(),
    ],
  });

  const [workPoolsQuery, filteredCountQuery, totalCountQuery] = results;

  return {
    workPools: workPoolsQuery.data ?? [],
    isLoadingWorkPools: workPoolsQuery.isLoading,
    isErrorWorkPools: workPoolsQuery.isError,
    errorWorkPools: workPoolsQuery.error,

    filteredCount: filteredCountQuery.data ?? 0,
    isLoadingFilteredCount: filteredCountQuery.isLoading,
    isErrorFilteredCount: filteredCountQuery.isError,

    totalCount: totalCountQuery?.data ?? filteredCountQuery.data ?? 0,
    isLoadingTotalCount: totalCountQuery?.isLoading ?? false,
    isErrorTotalCount: totalCountQuery?.isError ?? false,

    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
};

/**
 * Data loader for the useWorkPools hook, used by TanStack Router
 */
useWorkPools.loader = ({
  deps,
  context,
}: {
  deps: UseWorkPoolsOptions;
  context: { queryClient: QueryClient };
}) =>
  Promise.all([
    context.queryClient.ensureQueryData(buildWorkPoolsQuery(deps)),
    context.queryClient.ensureQueryData(buildCountQuery(deps)),
    context.queryClient.ensureQueryData(buildCountQuery()),
  ]);

type UseCreateWorkPoolOptions = {
  onSuccess: () => void;
  onError: (error: Error) => void;
};

/**
 * Hook for creating a new work pool
 */
export const useCreateWorkPool = ({
  onSuccess,
  onError,
}: UseCreateWorkPoolOptions) => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { mutate: createWorkPool, ...rest } = useMutation({
    mutationFn: (workPool: components["schemas"]["WorkPoolCreate"]) => {
      return getQueryService().POST("/work_pools/", {
        body: workPool,
      });
    },
    onSettled: async () => {
      return await queryClient.invalidateQueries({
        predicate: (query) => startsWith(query.queryKey, workPoolKeys.all),
      });
    },
    onSuccess: () => {
      toast({
        title: "Work pool created",
      });
      onSuccess();
    },
    onError,
  });

  return { createWorkPool, ...rest };
};

type UseUpdateWorkPoolProps = {
  onSuccess: () => void;
  onError: (error: Error) => void;
};

type WorkPoolUpdateWithName = components["schemas"]["WorkPoolUpdate"] & {
  name: string;
};

/**
 * Hook for updating an existing work pool
 */
export const useUpdateWorkPool = ({
  onSuccess,
  onError,
}: UseUpdateWorkPoolProps) => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { mutate: updateWorkPool, ...rest } = useMutation({
    mutationFn: (workPool: WorkPoolUpdateWithName) => {
      const { name, ...body } = workPool;
      return getQueryService().PATCH("/work_pools/{name}", {
        params: { path: { name } },
        body,
      });
    },
    onSettled: async () => {
      return await queryClient.invalidateQueries({
        predicate: (query) => startsWith(query.queryKey, workPoolKeys.all),
      });
    },
    onSuccess: () => {
      toast({
        title: "Work pool updated",
      });
      onSuccess();
    },
    onError,
  });

  return { updateWorkPool, ...rest };
}; 