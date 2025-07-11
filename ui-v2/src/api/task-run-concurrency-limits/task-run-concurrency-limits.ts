import {
	queryOptions,
	useMutation,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type TaskRunConcurrencyLimit = components["schemas"]["ConcurrencyLimit"];
export type TaskRunConcurrencyLimitsFilter =
	components["schemas"]["Body_read_concurrency_limits_concurrency_limits_filter_post"];

/**
 * ```
 *  🏗️ Task run concurrency limits queries construction 👷
 *  all   =>          ['task-run-concurrency-limits'] // key to match ['task-run-concurrency-limits', ...
 *  list  =>          ['task-run-concurrency-limits', 'list'] // key to match ['task-run-concurrency-limits', 'list', ...
 *                    ['task-run-concurrency-limits', 'list', { ...filter1 }]
 *                    ['task-run-concurrency-limits', 'list', { ...filter2 }]
 *  details =>        ['task-run-concurrency-limits', 'details'] // key to match ['task-run-concurrency-limits', 'details', ...
 *                    ['task-run-concurrency-limits', 'details', id1]
 *                    ['task-run-concurrency-limits', 'details', id2]
 *  activeTaskRuns => ['task-run-concurrency-limits', 'details', 'active-task-runs'] // key to match ['task-run-concurrency-limits', 'details', 'active-runs', ...
 *                    ['task-run-concurrency-limits', 'details', 'active-task-runs', id1]
 *                    ['task-run-concurrency-limits', 'details', 'active-task-runs', id2]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["task-run-concurrency-limits"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: TaskRunConcurrencyLimitsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
	activeTaskRuns: () =>
		[...queryKeyFactory.details(), "active-task-runs"] as const,
	activeTaskRun: (id: string) =>
		[...queryKeyFactory.activeTaskRuns(), id] as const,
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
		refetchInterval: 30_000,
	});

const fetchTaskRunConcurrencyLimit = async (id: string) => {
	// GET task-run-concurrency-limit by id
	const res = await getQueryService().GET("/concurrency_limits/{id}", {
		params: { path: { id } },
	});
	if (!res.data) {
		throw new Error("'data' expected");
	}
	return res.data;
};

export const buildDetailTaskRunConcurrencyLimitsQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: () => fetchTaskRunConcurrencyLimit(id),
	});

/**
 *
 * @param filter
 * @returns list of task run concurrency limits as a SuspenseQueryResult object
 */
export const useListTaskRunConcurrencyLimits = (
	filter: TaskRunConcurrencyLimitsFilter = { offset: 0 },
) => useSuspenseQuery(buildListTaskRunConcurrencyLimitsQuery(filter));

/**
 *
 * @returns details of task run concurrency limits as a SuspenseQueryResult object
 */
export const useGetTaskRunConcurrencyLimit = (id: string) =>
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
 *     console.log('Task Run concurrency limit tag reset successfully');
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

const fetchActiveTaskRunDetails = async (activeSlots: Array<string>) => {
	const taskRuns = await getQueryService().POST("/task_runs/filter", {
		body: {
			task_runs: {
				id: { any_: activeSlots },
				operator: "or_",
			},
			sort: "NAME_DESC",
			offset: 0,
		},
	});
	if (!taskRuns.data) {
		throw new Error("'data' expected");
	}
	const taskRunsWithFlows: Array<components["schemas"]["TaskRun"]> = [];
	const taskRunsOnly: Array<components["schemas"]["TaskRun"]> = [];

	for (const taskRun of taskRuns.data) {
		if (taskRun.flow_run_id) {
			taskRunsWithFlows.push(taskRun);
		} else {
			taskRunsOnly.push(taskRun);
		}
	}

	const activeTaskRunsWithoutFlows = taskRunsOnly.map((taskRun) => ({
		taskRun,
		flowRun: null,
		flow: null,
	}));

	// Early exit if there's no task with parent flows
	if (taskRunsWithFlows.length === 0) {
		return activeTaskRunsWithoutFlows;
	}

	// Now get parent flow information for tasks with parent flows
	const flowRunsIds = taskRunsWithFlows.map(
		(taskRun) => taskRun.flow_run_id as string,
	);

	// Get Flow Runs info
	const flowRuns = await getQueryService().POST("/flow_runs/filter", {
		body: {
			flow_runs: {
				id: { any_: flowRunsIds },
				operator: "or_",
			},
			sort: "NAME_DESC",
			offset: 0,
		},
	});
	if (!flowRuns.data) {
		throw new Error("'data' expected");
	}
	const hasSameFlowID = flowRuns.data.every(
		(flowRun) => flowRun.flow_id === flowRuns.data[0].flow_id,
	);
	if (!hasSameFlowID) {
		throw new Error("Flow runs has mismatching 'flow_id'");
	}
	const flowID = flowRuns.data[0].flow_id;

	// Get Flow info
	const flow = await getQueryService().GET("/flows/{id}", {
		params: { path: { id: flowID } },
	});

	if (!flow.data) {
		throw new Error("'data' expected");
	}

	// Normalize data per active slot :
	/**
	 *
	 *                   -> active_slot (task_run_id 1) -> flow_run (flow_run_id 1)
	 *  concurrencyLimit -> active_slot (task_run_id 2) -> flow_run (flow_run_id 2) -> flow (flow_id)
	 *                   -> active_slot (task_run_id 3) -> flow_run (flow_run_id 3)
	 *
	 */
	const activeTaskRunsWithFlows = taskRunsWithFlows.map((taskRunsWithFlow) => {
		const flowRun = flowRuns.data.find(
			(flowRun) => flowRun.id === taskRunsWithFlow.flow_run_id,
		);

		if (!flowRun) {
			throw new Error('"Expected to find flowRun');
		}

		return {
			taskRun: taskRunsWithFlow,
			flowRun,
			flow: flow.data,
		};
	});

	return [...activeTaskRunsWithFlows, ...activeTaskRunsWithoutFlows];
};

/**
 *
 * @param id
 * @returns query options for a task-run concurrency limit with active run details that includes details on task run, flow run, and flow
 */
export const buildConcurrenyLimitDetailsActiveRunsQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.activeTaskRun(id),
		queryFn: async () => {
			const taskRunConcurrencyLimit = await fetchTaskRunConcurrencyLimit(id);
			if (!taskRunConcurrencyLimit.active_slots) {
				throw new Error("'active_slots' expected");
			}

			const activeTaskRunsPromise = fetchActiveTaskRunDetails(
				taskRunConcurrencyLimit.active_slots,
			);

			return {
				taskRunConcurrencyLimit,
				activeTaskRunsPromise, // defer to return promise
			};
		},
	});
