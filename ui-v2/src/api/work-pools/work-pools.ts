import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type WorkPool = components["schemas"]["WorkPool"];
export type WorkPoolCreate = components["schemas"]["WorkPoolCreate"];
export type WorkPoolsFilter =
	components["schemas"]["Body_read_work_pools_work_pools_filter_post"];
export type WorkPoolsCountFilter =
	components["schemas"]["Body_count_work_pools_work_pools_count_post"];
export type WorkPoolWorker = components["schemas"]["WorkerResponse"];

/**
 * Query key factory for work pools-related queries
 *
 * @property {function} all - Returns base key for all work pool queries
 * @property {function} lists - Returns key for all list-type work pool queries
 * @property {function} list - Generates key for specific filtered work pool queries
 * @property {function} counts - Returns key for all count-type work pool queries
 * @property {function} count - Generates key for specific filtered count queries
 *
 * ```
 * all			=>   ['work-pools']
 * lists		=>   ['work-pools', 'list']
 * list			=>   ['work-pools', 'list', { ...filter }]
 * counts		=>   ['work-pools', 'counts']
 * count		=>   ['work-pools', 'counts', { ...filter }]
 * details		=>   ['work-pools', 'details']
 * detail		=>   ['work-pools', 'details', workPoolName]
 * workersLists	=>   ['work-pools', 'workers']
 * workersList	=>   ['work-pools', 'workers', workPoolName]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["work-pools"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: WorkPoolsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (filter: WorkPoolsCountFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (name: string) => [...queryKeyFactory.details(), name] as const,
	detailByName: (name: string) =>
		[...queryKeyFactory.details(), "by-name", name] as const,
	workersLists: () => [...queryKeyFactory.all(), "workers"] as const,
	workersList: (workPoolName: string) =>
		[...queryKeyFactory.workersLists(), workPoolName] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching filtered work pools
 *
 * @param filter - Filter options including:
 *   - limit: Number of items per page (default: 10)
 *   - offset: Offset of results based on the limit
 *   - work_pools: Optional work pools-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildFilterWorkPoolsQuery({
 *   limit: 100,
 *   offset: 0
 * }));
 * ```
 */
export const buildFilterWorkPoolsQuery = (
	filter: WorkPoolsFilter = { offset: 0 },
	{ enabled = true }: { enabled?: boolean } = {},
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/work_pools/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		enabled,
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for counting workpools based on filter criteria
 *
 * @param filter - Filter options for the work pool count query including:
 *   - offset: Number of items to skip (default: 0)
 *   - sort: Sort order for results
 *   - work_pools: Optional work pools-specific filters
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildCountWorkPoolsQuery({
 *   offset: 0,
 *   limit: 10,
 *   sort: "NAME_ASC",
 *   work_pools: {
 *     name: { like_: "my-work-pool" }
 *   }
 * }));
 * ```
 */
export const buildCountWorkPoolsQuery = (filter: WorkPoolsCountFilter = {}) =>
	queryOptions({
		queryKey: queryKeyFactory.count(filter),
		queryFn: async (): Promise<number> => {
			const res = await getQueryService().POST("/work_pools/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for getting a work pool details
 *
 * @param name - Work pool name to get details of
 * @returns Query configuration object for use with TanStack Query
 */
export const buildGetWorkPoolQuery = (name: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(name),
		queryFn: async () => {
			const res = await getQueryService().GET("/work_pools/{name}", {
				params: { path: { name } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		placeholderData: keepPreviousData,
	});

/**
 * Hook for pausing a work pool
 * @returns Mutation for pausing a work pool
 */
export const usePauseWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: pauseWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: true,
				},
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});
	return { pauseWorkPool, ...rest };
};

/**
 * Hook for resuming a work pool
 * @returns Mutation for resuming a work pool
 */
export const useResumeWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: resumeWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: false,
				},
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});

	return { resumeWorkPool, ...rest };
};

/**
 * Hook for deleting a work pool
 * @returns Mutation for deleting a work pool
 */
export const useDeleteWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().DELETE("/work_pools/{name}", {
				params: { path: { name } },
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});

	return { deleteWorkPool, ...rest };
};

/**
 * Hook for creating a work pool
 * @returns Mutation for creating a work pool
 */
export const useCreateWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: createWorkPool, ...rest } = useMutation({
		mutationFn: (workPool: WorkPoolCreate) =>
			getQueryService().POST("/work_pools/", {
				body: workPool,
			}),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.counts(),
			});
		},
	});

	return { createWorkPool, ...rest };
};

/**
 * Builds a query configuration for fetching work pool workers
 *
 * @param workPoolName - Name of the work pool to fetch workers for
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildListWorkPoolWorkersQuery('my-work-pool'));
 * ```
 */
export const buildListWorkPoolWorkersQuery = (workPoolName: string) =>
	queryOptions({
		queryKey: queryKeyFactory.workersList(workPoolName),
		queryFn: async (): Promise<WorkPoolWorker[]> => {
			const res = await getQueryService().POST(
				"/work_pools/{work_pool_name}/workers/filter",
				{
					params: { path: { work_pool_name: workPoolName } },
					body: {
						offset: 0,
					},
				},
			);
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		refetchInterval: 30000,
		placeholderData: keepPreviousData,
	});

/**
 * Hook for deleting a work pool worker
 * @returns Mutation for deleting a work pool worker
 */
export const useDeleteWorker = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteWorker, ...rest } = useMutation({
		mutationFn: ({
			workPoolName,
			workerName,
		}: {
			workPoolName: string;
			workerName: string;
		}) =>
			getQueryService().DELETE("/work_pools/{work_pool_name}/workers/{name}", {
				params: {
					path: {
						work_pool_name: workPoolName,
						name: workerName,
					},
				},
			}),
		onSuccess: (_, { workPoolName }) => {
			// Invalidate workers list for the work pool
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.workersList(workPoolName),
			});

			// Also invalidate work pool details which may show worker count
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});

	return { deleteWorker, ...rest };
};
