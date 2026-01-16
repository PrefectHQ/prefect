import {
	keepPreviousData,
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { Deployment } from "@/api/deployments";
import type { Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type FlowRun = components["schemas"]["FlowRunResponse"];
export type FlowRunWithFlow = FlowRun & {
	flow: Flow;
};
export type FlowRunWithDeploymentAndFlow = FlowRun & {
	deployment: Deployment;
	flow: Flow;
};
export type FlowRunsFilter =
	components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"];

export type FlowRunsPaginateFilter =
	components["schemas"]["Body_paginate_flow_runs_flow_runs_paginate_post"];

export type FlowRunsCountFilter =
	components["schemas"]["Body_count_flow_runs_flow_runs_count_post"];

export type FlowRunHistoryFilter =
	components["schemas"]["Body_read_flow_run_history_ui_flow_runs_history_post"];

export type SimpleFlowRun = components["schemas"]["SimpleFlowRun"];

export type CreateNewFlowRun = components["schemas"]["DeploymentFlowRunCreate"];

/**
 * Converts a FlowRunsFilter to a FlowRunsCountFilter by extracting only the
 * filter properties that are valid for the count endpoint.
 *
 * The count endpoint does not accept sort, limit, or offset parameters.
 *
 * @param filter - The FlowRunsFilter to convert
 * @returns A FlowRunsCountFilter with only the valid filter properties
 */
export function toFlowRunsCountFilter(
	filter: FlowRunsFilter,
): FlowRunsCountFilter {
	return {
		flows: filter.flows,
		flow_runs: filter.flow_runs,
		task_runs: filter.task_runs,
		deployments: filter.deployments,
		work_pools: filter.work_pools,
		work_pool_queues: filter.work_pool_queues,
	};
}

/**
 * The request body for setting a flow run state
 */
type SetFlowRunStateBody =
	components["schemas"]["Body_set_flow_run_state_flow_runs__id__set_state_post"];

/**
 * Parameters for setting a flow run state, combining the path param with the request body
 */
type SetFlowRunStateParams = {
	id: string;
} & SetFlowRunStateBody;

/**
 * Query key factory for flows-related queries
 *
 * @property {function} all - Returns base key for all flow run queries
 * @property {function} lists - Returns key for all list-type flow run queries
 * @property {function} list - Generates key for a specific filtered flow run query
 * @property {function} paginate - Returns key for all paginated flow run queries
 * @property {function} counts - Returns key for all count-type flow run queries
 * @property {function} count - Generates key for a specific count query
 * @property {function} lateness - Returns key for all lateness-type flow run queries
 * @property {function} latenessWithFilter - Generates key for a specific lateness query with filter
 * @property {function} details - Returns key for all details-type flow run queries
 * @property {function} detail - Generates key for a specific details-type flow run query
 *
 * ```
 * all    	=> 	['flowRuns']
 * lists  	=>  ['flowRuns', 'list']
 * filter	=>	['flowRuns', 'list', 'filter', {...filters}]
 * paginate	=>	['flowRuns', 'list', 'paginate', {...filters}]
 * counts	=>	['flowRuns', 'count']
 * count	=>	['flowRuns', 'count', {...filters}]
 * lateness	=>	['flowRuns', 'lateness']
 * latenessWithFilter	=>	['flowRuns', 'lateness', {...filters}]
 * details	=>	['flowRuns', 'details']
 * detail	=>	['flowRuns', 'details', id]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["flowRuns"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	filter: (filter: FlowRunsFilter) =>
		[...queryKeyFactory.lists(), "filter", filter] as const,
	paginate: (filter: FlowRunsPaginateFilter) =>
		[...queryKeyFactory.lists(), "paginate", filter] as const,
	counts: () => [...queryKeyFactory.all(), "count"] as const,
	count: (filter: FlowRunsCountFilter) =>
		[...queryKeyFactory.counts(), filter] as const,
	lateness: () => [...queryKeyFactory.all(), "lateness"] as const,
	latenessWithFilter: (filter: FlowRunsFilter) =>
		[...queryKeyFactory.lateness(), filter] as const,
	history: () => [...queryKeyFactory.all(), "history"] as const,
	historyWithFilter: (filter: FlowRunHistoryFilter) =>
		[...queryKeyFactory.history(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

/**
 * Builds a query configuration for fetching filtered flow runs
 *
 * @param filter - Filter parameters for the flow runs query.
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data, isLoading, error } = useQuery(buildFilterFlowRunsQuery({
 *   offset: 0,
 *   sort: "CREATED_DESC",
 *   flow_runs: {
 *     name: { like_: "my-flow-run" }
 *   }
 * }));
 * ```
 */
export const buildFilterFlowRunsQuery = (
	filter: FlowRunsFilter = {
		sort: "ID_DESC",
		offset: 0,
	},
	refetchInterval = 30_000,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.filter(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/flow_runs/filter", {
				body: filter,
			});
			return res.data ?? ([] satisfies FlowRun[]);
		},
		staleTime: 1000,
		refetchInterval,
	});
};

/**
 * Builds a query configuration for fetching filtered flow runs
 *
 * @param filter - Filter parameters for the flow runs pagination query.
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildPaginateFlowRunsQuery());
 * ```
 */
export const buildPaginateFlowRunsQuery = (
	filter: FlowRunsPaginateFilter = {
		page: 1,
		sort: "START_TIME_DESC",
	},
	refetchInterval = 30_000,
) => {
	return queryOptions({
		queryKey: queryKeyFactory.paginate(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/flow_runs/paginate", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		placeholderData: keepPreviousData,
		staleTime: 1000,
		refetchInterval,
	});
};

/**
 * Builds a query configuration for fetching a flow run by id
 *
 * @param id - The id of the flow run to fetch
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useSuspenseQuery(buildGetFlowRunDetailsQuery("id-0"));
 * ```
 */
export const buildGetFlowRunDetailsQuery = (id: string) => {
	return queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await (await getQueryService()).GET("/flow_runs/{id}", {
				params: { path: { id } },
			});

			if (!res.data) {
				throw new Error(
					`Received empty response from server for flow run ${id}`,
				);
			}
			return res.data;
		},
	});
};

/**
 * Builds a query configuration for counting flow runs
 *
 * @param filter - Filter parameters for the flow runs count query.
 * @param refetchInterval - Interval for refetching the count (default 60 seconds for late runs)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: lateRunsCount } = useSuspenseQuery(buildCountFlowRunsQuery({
 *   flow_runs: {
 *     state: { type: { any_: ["LATE"] } }
 *   }
 * }));
 * ```
 */
export const buildCountFlowRunsQuery = (
	filter: FlowRunsCountFilter = {},
	refetchInterval = 60000, // Check every minute for late runs
) =>
	queryOptions({
		queryKey: queryKeyFactory.count(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/flow_runs/count", {
				body: filter,
			});
			return res.data ?? 0;
		},
		refetchInterval,
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for fetching the average lateness of flow runs
 *
 * @param filter - Filter parameters for the flow runs
 * @param refetchInterval - Interval for refetching the average lateness (default 30 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: avgLateness } = useSuspenseQuery(buildAverageLatenessFlowRunsQuery({
 *   flow_runs: {
 *     state: { name: { any_: ["Late"] } }
 *   }
 * }));
 * ```
 */
export const buildAverageLatenessFlowRunsQuery = (
	filter: FlowRunsFilter = {
		sort: "ID_DESC",
		offset: 0,
	},
	refetchInterval = 30_000,
) =>
	queryOptions({
		queryKey: queryKeyFactory.latenessWithFilter(filter),
		queryFn: async (): Promise<number | null> => {
			const res = await (await getQueryService()).POST("/flow_runs/lateness", {
				body: filter,
			});
			return res.data ?? null;
		},
		refetchInterval,
		placeholderData: keepPreviousData,
	});

/**
 * Builds a query configuration for fetching flow run history for scatter plot visualization
 *
 * @param filter - Filter parameters for the flow run history query.
 * @param refetchInterval - Interval for refetching the history (default 30 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: history } = useSuspenseQuery(buildFlowRunHistoryQuery({
 *   sort: "EXPECTED_START_TIME_DESC",
 *   limit: 1000
 * }));
 * ```
 */
export const buildFlowRunHistoryQuery = (
	filter: FlowRunHistoryFilter = {
		sort: "EXPECTED_START_TIME_DESC",
		limit: 1000,
		offset: 0,
	},
	refetchInterval = 30_000,
) =>
	queryOptions({
		queryKey: queryKeyFactory.historyWithFilter(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/ui/flow_runs/history",
				{
					body: filter,
				},
			);
			return res.data ?? ([] satisfies SimpleFlowRun[]);
		},
		placeholderData: keepPreviousData,
		staleTime: 1000,
		refetchInterval,
	});

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

/**
 * Hook for deleting a flow run
 *
 * @returns Mutation object for deleting a flow run with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteFlowRun, isLoading } = useDeleteFlowRun();
 *
 * deleteflowRun(id, {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *     console.log('Flow run deleted successfully');
 *   },
 *    (error) => {
 *     // Handle error
 *     console.error('Failed to delete flow run:', error);
 *   }
 * });
 * ```
 */
export const useDeleteFlowRun = () => {
	const queryClient = useQueryClient();
	const { mutate: deleteFlowRun, ...rest } = useMutation({
		mutationFn: async (id: string) =>
			(await getQueryService()).DELETE("/flow_runs/{id}", {
				params: { path: { id } },
			}),
		onSuccess: () => {
			// After a successful creation, invalidate only list queries to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		deleteFlowRun,
		...rest,
	};
};

type MutateCreateFlowRun = {
	id: string;
} & CreateNewFlowRun;
/**
 * Hook for creating a new flow run from an automation
 *
 * @returns Mutation object for creating a flow run with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createDeploymentFlowRun, isLoading } = useDeploymentCreateFlowRun();
 *
 * createDeploymentFlowRun({ deploymentId, ...body }, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Flow run created successfully');
 *   },
 *    (error) => {
 *     // Handle error
 *     console.error('Failed to create flow run:', error);
 *   }
 * });
 * ```
 */
export const useDeploymentCreateFlowRun = () => {
	const queryClient = useQueryClient();
	const { mutate: createDeploymentFlowRun, ...rest } = useMutation({
		mutationFn: async ({ id, ...body }: MutateCreateFlowRun) => {
			const res = await (await getQueryService()).POST(
				"/deployments/{id}/create_flow_run",
				{
					body,
					params: { path: { id } },
				},
			);

			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		onSuccess: () => {
			// After a successful creation, invalidate only list queries to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		createDeploymentFlowRun,
		...rest,
	};
};

/**
 * Hook for changing a flow run's state
 *
 * @returns Mutation object for setting a flow run state with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { setFlowRunState, isLoading } = useSetFlowRunState();
 *
 * setFlowRunState({
 *   id: "flow-run-id",
 *   state: { type: "COMPLETED" },
 *   message: "State changed by user"
 * });
 * ```
 */
export const useSetFlowRunState = () => {
	const queryClient = useQueryClient();
	const { mutate: setFlowRunState, ...rest } = useMutation({
		mutationFn: async ({ id, ...params }: SetFlowRunStateParams) => {
			const res = await (await getQueryService()).POST(
				"/flow_runs/{id}/set_state",
				{
					params: { path: { id } },
					body: params,
				},
			);

			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		onMutate: async ({ id, state }) => {
			await queryClient.cancelQueries({ queryKey: queryKeyFactory.detail(id) });

			const previousFlowRun = queryClient.getQueryData<FlowRun>(
				queryKeyFactory.detail(id),
			);

			if (previousFlowRun?.state) {
				queryClient.setQueryData<FlowRun>(queryKeyFactory.detail(id), {
					...previousFlowRun,
					state: {
						id: previousFlowRun.state.id,
						type: state.type,
						name: state.name ?? previousFlowRun.state.name,
						message: state.message ?? previousFlowRun.state.message,
						timestamp: new Date().toISOString(),
						data: previousFlowRun.state.data,
						state_details: previousFlowRun.state.state_details,
					},
				});
			}

			return { previousFlowRun };
		},
		onError: (_err, { id }, context) => {
			// Roll back optimistic update on error
			if (context?.previousFlowRun) {
				queryClient.setQueryData(
					queryKeyFactory.detail(id),
					context.previousFlowRun,
				);
			}
		},
		onSettled: (_data, _error, { id }) => {
			void Promise.all([
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.lists() }),
				queryClient.invalidateQueries({ queryKey: queryKeyFactory.detail(id) }),
			]);
		},
	});
	return {
		setFlowRunState,
		...rest,
	};
};
