import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type WorkPoolQueueStatus = "ready" | "paused" | "not_ready";

export interface WorkPoolQueue {
	id: string;
	created: string | null;
	updated: string | null;
	name: string;
	description: string | null;
	is_paused: boolean;
	concurrency_limit: number | null;
	priority: number;
	work_pool_id: string | null;
	work_pool_name: string;
	last_polled: string | null;
	status: WorkPoolQueueStatus;
}

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
			const res = await getQueryService().POST(
				"/work_pools/{work_pool_name}/queues/filter",
				{
					params: { path: { work_pool_name: workPoolName } },
					body: { offset: 0 },
				},
			);

			if (!res.data) {
				throw new Error("'data' expected");
			}

			// Transform the response to include work_pool_name and status
			return res.data.map(
				(queue): WorkPoolQueue => ({
					id: queue.id,
					created: queue.created,
					updated: queue.updated,
					name: queue.name,
					description: queue.description,
					is_paused: queue.is_paused,
					concurrency_limit: queue.concurrency_limit ?? null,
					priority: queue.priority,
					work_pool_id: queue.work_pool_id ?? null,
					work_pool_name: workPoolName,
					last_polled: queue.last_polled ?? null,
					status: getQueueStatus(queue),
				}),
			);
		},
		refetchInterval: 30000, // 30 seconds for real-time updates
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
			const res = await getQueryService().GET("/work_queues/{id}", {
				params: { path: { id: queueName } }, // Assuming queueName can be used as ID
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}

			// Transform the response to include work_pool_name and status
			return {
				id: res.data.id,
				created: res.data.created,
				updated: res.data.updated,
				name: res.data.name,
				description: res.data.description,
				is_paused: res.data.is_paused,
				concurrency_limit: res.data.concurrency_limit ?? null,
				priority: res.data.priority,
				work_pool_id: res.data.work_pool_id ?? null,
				work_pool_name: workPoolName,
				last_polled: res.data.last_polled ?? null,
				status: getQueueStatus(res.data),
			};
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
		mutationFn: ({ queueName }: { workPoolName: string; queueName: string }) =>
			getQueryService().PATCH("/work_queues/{id}", {
				params: { path: { id: queueName } },
				body: {
					is_paused: true,
				},
			}),

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
		mutationFn: ({ queueName }: { workPoolName: string; queueName: string }) =>
			getQueryService().PATCH("/work_queues/{id}", {
				params: { path: { id: queueName } },
				body: {
					is_paused: false,
				},
			}),

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
 * Hook for deleting a work pool queue
 * @returns Mutation for deleting a work pool queue
 */
export const useDeleteWorkPoolQueueMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: ({ queueName }: { workPoolName: string; queueName: string }) =>
			getQueryService().DELETE("/work_queues/{id}", {
				params: { path: { id: queueName } },
			}),

		onSuccess: (_, { workPoolName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
		},
	});
};

// ----------------------------
//  Helper Functions
// ----------------------------

/**
 * Determines the status of a work queue based on its properties
 */
function getQueueStatus(
	queue: components["schemas"]["WorkQueueResponse"],
): WorkPoolQueueStatus {
	if (queue.is_paused) {
		return "paused";
	}

	// For now, assume a queue is ready if it's not paused
	// This logic can be extended based on actual health checks or other criteria
	return "ready";
}
