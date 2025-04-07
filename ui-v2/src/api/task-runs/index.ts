import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "../prefect";
import { getQueryService } from "../service";

export type TaskRun = components["schemas"]["UITaskRun"];

export type TaskRunsFilter =
	components["schemas"]["Body_read_task_runs_task_runs_filter_post"];

type SetTaskRunStateBody =
	components["schemas"]["Body_set_task_run_state_task_runs__id__set_state_post"];

type SetTaskRunStateParams = {
	id: string;
} & SetTaskRunStateBody;

/**
 * Query key factory for task-related queries
 *
 * @property {function} all - Returns base key for all task run queries
 * @property {function} lists - Returns key for all list-type task run queries
 * @property {function} list - Generates key for a specific filtered task run query
 * @property {function} counts - Returns key for all count-type task run queries
 * @property {function} flowRunsCount - Generates key for a specific flow run count task run query
 * @property {function} details - Returns key for all details-type task run queries
 * @property {function} detail - Generates key for a specific details-type task run query
 *
 * ```
 * all			=>   ['taskRuns']
 * lists		=>   ['taskRuns', 'list']
 * list			=>   ['taskRuns', 'list', { ...filter }]
 * counts		=>   ['taskRuns', 'count']
 * flowRunsCount	=>   ['taskRuns', 'count', 'flow-runs', ["id-0", "id-1"]]
 * details		=>   ['taskRuns', 'details']
 * detail		=>   ['taskRuns', 'details', id]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["taskRuns"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: TaskRunsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	counts: () => [...queryKeyFactory.all(), "count"] as const,
	flowRunsCount: (flowRunIds: Array<string>) => [
		...queryKeyFactory.counts(),
		"flow-runs",
		flowRunIds,
	],
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

/**
 * Builds a query configuration for fetching filtered task runs
 *
 * @param filter - Filter parameters for the task runs query.
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data, isLoading, error } = useQuery(buildListTaskRunsQuery({
 *   offset: 0,
 *   sort: "CREATED_DESC",
 *   task_runs: {
 *     name: { like_: "my-task-run" }
 *   }
 * }));
 * ```
 */
export const buildListTaskRunsQuery = (
	filter: TaskRunsFilter = {
		sort: "ID_DESC",
		offset: 0,
	},
	refetchInterval = 30_000,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/task_runs/filter", {
				body: filter,
			});
			return res.data ?? [];
		},
		staleTime: 1000,
		refetchInterval,
	});
};

/**
 * Builds a query configuration for fetching flow runs task count
 *
 * @param flow_run_ids - Array of flow run ids
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildListTaskRunsQuery(["id-0", "id-1"]));
 * ```
 */
export const buildGetFlowRunsTaskRunsCountQuery = (
	flow_run_ids: Array<string>,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.flowRunsCount(flow_run_ids),
		queryFn: async () => {
			const res = await getQueryService().POST(
				"/ui/flow_runs/count-task-runs",
				{ body: { flow_run_ids } },
			);
			return res.data ?? {};
		},
	});
};

/**
 * Builds a query configuration for fetching a task run by id
 *
 * @param id - The id of the task run to fetch
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildGetTaskRunQuery("task-run-id"));
 * ```
 */
export const buildGetTaskRunQuery = (id: string) => {
	return queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/ui/task_runs/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error(
					`Received empty response from server for task run ${id}`,
				);
			}
			return res.data;
		},
	});
};

/**
 * Builds a query configuration for fetching task run details
 *
 * @param id - The id of the task run
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildGetTaskRunDetailsQuery("id-0"));
 * ```
 */
export const buildGetTaskRunDetailsQuery = (id: string) => {
	return queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/ui/task_runs/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error(
					`Received empty response from server for task run ${id}`,
				);
			}
			return res.data;
		},
	});
};

/**
 * Hook for changing a task run's state
 *
 * @returns Mutation object for setting a task run state with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { setTaskRunState, isLoading } = useSetTaskRunState();
 *
 * setTaskRunState({
 *   id: "task-run-id",
 *   state: { type: "COMPLETED" },
 *   message: "State changed by user"
 * });
 * ```
 */
export const useSetTaskRunState = () => {
	const queryClient = useQueryClient();
	const { mutate: setTaskRunState, ...rest } = useMutation({
		mutationFn: async ({ id, ...params }: SetTaskRunStateParams) => {
			const res = await getQueryService().POST("/task_runs/{id}/set_state", {
				params: { path: { id } },
				body: params,
			});

			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		onMutate: async ({ id, state }) => {
			await queryClient.cancelQueries({ queryKey: queryKeyFactory.detail(id) });

			const previousTaskRun = queryClient.getQueryData<TaskRun>(
				queryKeyFactory.detail(id),
			);

			if (previousTaskRun?.state) {
				queryClient.setQueryData<TaskRun>(queryKeyFactory.detail(id), {
					...previousTaskRun,
					state: {
						id: previousTaskRun.state.id,
						type: state.type,
						name: state.name ?? previousTaskRun.state.name,
						message: state.message ?? previousTaskRun.state.message,
						timestamp: new Date().toISOString(),
						data: previousTaskRun.state.data,
						state_details: previousTaskRun.state.state_details,
					},
				});
			}

			return { previousTaskRun };
		},
		onError: (err, { id }, context) => {
			// Roll back optimistic update on error
			if (context?.previousTaskRun) {
				queryClient.setQueryData(
					queryKeyFactory.detail(id),
					context.previousTaskRun,
				);
			}

			throw err instanceof Error
				? err
				: new Error("Failed to update task run state");
		},
		onSettled: (_data, _error, { id }) => {
			void Promise.all([
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.lists() }),
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.detail(id) }),
			]);
		},
	});
	return {
		setTaskRunState,
		...rest,
	};
};

/**
 * Hook for deleting a task run
 *
 * @returns Mutation object for deleting a task run with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteTaskRun, isLoading } = useDeleteTaskRun();
 * ```
 */
export const useDeleteTaskRun = () => {
	const queryClient = useQueryClient();
	const { mutate: deleteTaskRun, ...rest } = useMutation({
		mutationFn: async ({ id }: { id: string }) => {
			const res = await getQueryService().DELETE("/task_runs/{id}", {
				params: { path: { id } },
			});
			return res.data;
		},
		onSettled: () => {
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return { deleteTaskRun, ...rest };
};
