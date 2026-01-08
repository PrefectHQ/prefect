import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type WorkPoolQueueStatus = "READY" | "PAUSED" | "NOT_READY";

export type WorkPoolQueue = components["schemas"]["WorkQueueResponse"];

export type WorkPoolQueueCreate = components["schemas"]["WorkQueueCreate"];
export type WorkPoolQueueUpdate = components["schemas"]["WorkQueueUpdate"];

/**
 * Query key factory for work pool queues-related queries
 *
 * @property {function} all - Returns base key for all work pool queue queries
 * @property {function} lists - Returns key for all list-type work pool queue queries
 * @property {function} list - Generates key for specific work pool queue list
 * @property {function} details - Returns key for all detail-type work pool queue queries
 * @property {function} detail - Generates key for specific work pool queue detail
 *
 * ```
 * all			=>   ['work_pool_queues']
 * lists		=>   ['work_pool_queues', 'list']
 * list			=>   ['work_pool_queues', 'list', workPoolName]
 * details		=>   ['work_pool_queues', 'details']
 * detail		=>   ['work_pool_queues', 'details', workPoolName, queueName]
 * ```
 */
export const workPoolQueuesQueryKeyFactory = {
	all: () => ["work_pool_queues"] as const,
	lists: () => [...workPoolQueuesQueryKeyFactory.all(), "list"] as const,
	list: (workPoolName: string) =>
		[...workPoolQueuesQueryKeyFactory.lists(), workPoolName] as const,
	details: () => [...workPoolQueuesQueryKeyFactory.all(), "details"] as const,
	detail: (workPoolName: string, queueName: string) =>
		[
			...workPoolQueuesQueryKeyFactory.details(),
			workPoolName,
			queueName,
		] as const,
};

// ----------------------------
//  Query Options Factories
// ----------------------------

/**
 * Builds a query configuration for fetching work pool queues
 *
 * @param workPoolName - Name of the work pool to fetch queues for
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildListWorkPoolQueuesQuery('my-work-pool'));
 * ```
 */
export const buildListWorkPoolQueuesQuery = (workPoolName: string) =>
	queryOptions({
		queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
		queryFn: async (): Promise<WorkPoolQueue[]> => {
			// Use the existing work queues API to filter by work pool
			const res = await (await getQueryService()).POST(
				"/work_pools/{work_pool_name}/queues/filter",
				{
					params: { path: { work_pool_name: workPoolName } },
					body: { offset: 0 },
				},
			);

			if (!res.data) {
				throw new Error("'data' expected");
			}

			return res.data;
		},
		refetchInterval: 30000, // 30 seconds for real-time updates
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for fetching a work pool queue's details
 *
 * @param workPoolName - Name of the work pool
 * @param queueName - Name of the queue
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildWorkPoolQueueDetailsQuery('my-work-pool', 'my-queue'));
 * ```
 */
export const buildWorkPoolQueueDetailsQuery = (
	workPoolName: string,
	queueName: string,
) =>
	queryOptions({
		queryKey: workPoolQueuesQueryKeyFactory.detail(workPoolName, queueName),
		queryFn: async (): Promise<WorkPoolQueue> => {
			const res = await (await getQueryService()).GET(
				"/work_pools/{work_pool_name}/queues/{name}",
				{
					params: {
						path: { work_pool_name: workPoolName, name: queueName },
					},
				},
			);
			if (!res.data) {
				throw new Error("'data' expected");
			}

			return res.data;
		},
	});

// ----------------------------
//  Mutation Hooks
// ----------------------------

/**
 * Hook for pausing a work pool queue
 * @returns Mutation for pausing a work pool queue
 */
export const usePauseWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({
			workPoolName,
			queueName,
		}: {
			workPoolName: string;
			queueName: string;
		}) =>
			(await getQueryService()).PATCH(
				"/work_pools/{work_pool_name}/queues/{name}",
				{
					params: { path: { work_pool_name: workPoolName, name: queueName } },
					body: {
						is_paused: true,
					},
				},
			),

		onSuccess: (_, { workPoolName, queueName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.detail(workPoolName, queueName),
			});
		},
	});
};

/**
 * Hook for resuming a work pool queue
 * @returns Mutation for resuming a work pool queue
 */
export const useResumeWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({
			workPoolName,
			queueName,
		}: {
			workPoolName: string;
			queueName: string;
		}) =>
			(await getQueryService()).PATCH(
				"/work_pools/{work_pool_name}/queues/{name}",
				{
					params: { path: { work_pool_name: workPoolName, name: queueName } },
					body: {
						is_paused: false,
					},
				},
			),

		onSuccess: (_, { workPoolName, queueName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.detail(workPoolName, queueName),
			});
		},
	});
};

/**
 * Hook for creating a work pool queue
 * @returns Mutation for creating a work pool queue
 */
export const useCreateWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({
			workPoolName,
			workQueueData,
		}: {
			workPoolName: string;
			workQueueData: WorkPoolQueueCreate;
		}) =>
			(await getQueryService()).POST("/work_pools/{work_pool_name}/queues", {
				params: { path: { work_pool_name: workPoolName } },
				body: workQueueData,
			}),

		onSuccess: (_, { workPoolName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
		},
	});
};

/**
 * Hook for updating a work pool queue
 * @returns Mutation for updating a work pool queue
 */
export const useUpdateWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({
			workPoolName,
			queueName,
			workQueueData,
		}: {
			workPoolName: string;
			queueName: string;
			workQueueData: WorkPoolQueueUpdate;
		}) =>
			(await getQueryService()).PATCH(
				"/work_pools/{work_pool_name}/queues/{name}",
				{
					params: { path: { work_pool_name: workPoolName, name: queueName } },
					body: workQueueData,
				},
			),

		onSuccess: (_, { workPoolName, queueName, workQueueData }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.detail(workPoolName, queueName),
			});
			// If the queue was renamed, also invalidate the new name's detail query
			if (workQueueData.name && workQueueData.name !== queueName) {
				void queryClient.invalidateQueries({
					queryKey: workPoolQueuesQueryKeyFactory.detail(
						workPoolName,
						workQueueData.name,
					),
				});
			}
		},
	});
};

/**
 * Hook for deleting a work pool queue
 * @returns Mutation for deleting a work pool queue
 */
export const useDeleteWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({
			workPoolName,
			queueName,
		}: {
			workPoolName: string;
			queueName: string;
		}) =>
			(await getQueryService()).DELETE(
				"/work_pools/{work_pool_name}/queues/{name}",
				{
					params: { path: { work_pool_name: workPoolName, name: queueName } },
				},
			),

		onSuccess: (_, { workPoolName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
		},
	});
};
