import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";

export type TaskRunConcurrencyLimit = components["schemas"]["ConcurrencyLimit"];
export type TaskRunConcurrencyLimitsFilter =
	components["schemas"]["Body_read_concurrency_limits_concurrency_limits_filter_post"];

/**
 * ```
 *  🏗️ Task run concurrency limits queries construction 👷
 *  all   =>   ['task-run-concurrency-limits'] // key to match ['task-run-concurrency-limits', ...
 *  list  =>   ['task-run-concurrency-limits', 'list'] // key to match ['task-run-concurrency-limits', 'list', ...
 *             ['task-run-concurrency-limits', 'list', { ...filter1 }]
 *             ['task-run-concurrency-limits', 'list', { ...filter2 }]
 *  details => ['task-run-concurrency-limits', 'details'] // key to match ['task-run-concurrency-limits', 'details', ...
 *             ['task-run-concurrency-limits', 'details', id1]
 *             ['task-run-concurrency-limits', 'details', id2]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["task-run-concurrency-limits"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: TaskRunConcurrencyLimitsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListTaskRunConcurrencyLimitsQuery = (
	filter: TaskRunConcurrencyLimitsFilter = { offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/concurrency_limits/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
	});

export const buildDetailTaskRunConcurrencyLimitsQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/concurrency_limits/{id}", {
				params: { path: { id } },
			});
			return res.data as TaskRunConcurrencyLimit; // Expecting data to be truthy;
		},
	});

/**
 *
 * @param filter
 * @returns list of task run concurrency limits as a SuspenseQueryResult object
 */
export const useListGlobalConcurrencyLimits = (
	filter: TaskRunConcurrencyLimitsFilter = { offset: 0 },
) => useSuspenseQuery(buildListTaskRunConcurrencyLimitsQuery(filter));

/**
 *
 * @returns details of task run concurrency limits as a SuspenseQueryResult object
 */
export const useGetGlobalConcurrencyLimit = (id: string) =>
	useSuspenseQuery(buildDetailTaskRunConcurrencyLimitsQuery(id));

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

/**
 * Hook for deleting a task run concurrency limit
 *
 * @returns Mutation object for deleting a task run concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteTaskRunConcurrencyLimit } = useDeleteTaskRunConcurrencyLimit();
 *
 * // Delete a  taskRun concurrency limit by id or name
 * deleteTaskRunConcurrencyLimit('id-to-delete', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *   },
 *   onError: (error) => {
 *     console.error('Failed to delete task run concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useDeleteTaskRunConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: deleteTaskRunConcurrencyLimit, ...rest } = useMutation({
		mutationFn: (id: string) =>
			getQueryService().DELETE("/concurrency_limits/{id}", {
				params: { path: { id } },
			}),
		onSuccess: () => {
			// After a successful deletion, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		deleteTaskRunConcurrencyLimit,
		...rest,
	};
};

/**
 * Hook for creating a new task run concurrency limit
 *
 * @returns Mutation object for creating a task run concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createTaskRunConcurrencyLimit, isLoading } = useCreateTaskRunConcurrencyLimit();
 *
 * // Create a new task run concurrency limit
 * createTaskRunConcurrencyLimit({
 * 	tag: "my tag"
 * 	concurrency_limit: 9000
 * }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Task Run concurrency limit created successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to create task run concurrency limit:', error);
 *   }
 * });
 * ```
 */
export const useCreateTaskRunConcurrencyLimit = () => {
	const queryClient = useQueryClient();
	const { mutate: createTaskRunConcurrencyLimit, ...rest } = useMutation({
		mutationFn: (body: components["schemas"]["ConcurrencyLimitCreate"]) =>
			getQueryService().POST("/concurrency_limits/", {
				body,
			}),
		onSuccess: () => {
			// After a successful creation, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		createTaskRunConcurrencyLimit,
		...rest,
	};
};

/**
 * Hook for resetting a concurrency limit's active task runs based on the tag name
 *
 * @returns Mutation object for resetting a task run concurrency limit with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { resetTaskRunConcurrencyLimitTag, isLoading } = useResetTaskRunConcurrencyLimitTag();
 *
 * // Create a new task run concurrency limit
 * resetTaskRunConcurrencyLimitTag('my-tag', {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Task Run concurrency limit tag resetted successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to reset task run concurrency limit', error);
 *   }
 * });
 * ```
 */
export const useResetTaskRunConcurrencyLimitTag = () => {
	const queryClient = useQueryClient();
	const { mutate: resetTaskRunConcurrencyLimitTag, ...rest } = useMutation({
		mutationFn: (tag: string) =>
			getQueryService().POST("/concurrency_limits/tag/{tag}/reset", {
				params: { path: { tag } },
			}),
		onSuccess: () => {
			// After a successful reset, invalidate all to get an updated list and details list
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});
	return {
		resetTaskRunConcurrencyLimitTag,
		...rest,
	};
};
