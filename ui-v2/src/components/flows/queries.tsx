import type {
	MutationFunction,
	QueryFunction,
	QueryKey,
	QueryObserverOptions,
} from "@tanstack/react-query";
import { format } from "date-fns";
import type { FlowRunsFilter } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export const flowQueryParams = (
	flowId: string,
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: QueryKey;
	queryFn: QueryFunction<components["schemas"]["Flow"]>;
} => ({
	...queryParams,
	queryKey: ["flows", flowId] as const,
	queryFn: async (): Promise<components["schemas"]["Flow"]> => {
		const response = await getQueryService()
			.GET("/flows/{id}", {
				params: { path: { id: flowId } },
			})
			.then((response) => response.data);
		return response as components["schemas"]["Flow"];
	},
});

export const buildFlowRunsFilter = (
	flowId: string,
	filter: FlowRunsFilter,
): FlowRunsFilter => ({
	...filter,
	flows: {
		...filter.flows,
		operator: "and_" as const,
		id: { any_: [flowId] },
	},
});

export const flowRunsQueryParams = (
	id: string,
	body: components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"],
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["flowRun", string];
	queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
} => ({
	...queryParams,
	queryKey: ["flowRun", JSON.stringify({ flowId: id, ...body })] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/flow_runs/filter", {
				body: {
					...buildFlowRunsFilter(id, body),
				},
			})
			.then((response) => response.data);
		return response as components["schemas"]["FlowRunResponse"][];
	},
});

export const getLatestFlowRunsQueryParams = (
	id: string,
	n: number,
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["flowRun", string];
	queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
} => ({
	...queryParams,
	queryKey: [
		"flowRun",
		JSON.stringify({
			flowId: id,
			offset: 0,
			limit: n,
			sort: "START_TIME_DESC",
		}),
	] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/flow_runs/filter", {
				body: {
					flows: { operator: "and_" as const, id: { any_: [id] } },
					flow_runs: {
						operator: "and_" as const,
						start_time: {
							before_: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
							is_null_: false,
						},
					},
					offset: 0,
					limit: n,
					sort: "START_TIME_DESC",
				},
			})
			.then((response) => response.data);
		return response as components["schemas"]["FlowRunResponse"][];
	},
});

export const getNextFlowRunsQueryParams = (
	id: string,
	n: number,
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["flowRun", string];
	queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
} => ({
	...queryParams,
	queryKey: [
		"flowRun",
		JSON.stringify({
			flowId: id,
			offset: 0,
			limit: n,
			sort: "EXPECTED_START_TIME_ASC",
		}),
	] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/flow_runs/filter", {
				body: {
					flows: { operator: "and_" as const, id: { any_: [id] } },
					flow_runs: {
						operator: "and_" as const,
						expected_start_time: {
							after_: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
						},
					},
					offset: 0,
					limit: n,
					sort: "EXPECTED_START_TIME_ASC",
				},
			})
			.then((response) => response.data);
		return response as components["schemas"]["FlowRunResponse"][];
	},
});

export const flowRunsCountQueryParams = (
	id: string,
	body?: components["schemas"]["Body_count_flow_runs_flow_runs_count_post"],
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["flowRunCount", string];
	queryFn: () => Promise<number>;
} => ({
	...queryParams,
	queryKey: ["flowRunCount", JSON.stringify({ flowId: id, ...body })] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/flow_runs/count", {
				body: {
					...body,
					flows: {
						...body?.flows,
						operator: "and_" as const,
						id: { any_: [id] },
					},
					flow_runs: {
						operator: "and_" as const,
						expected_start_time: {
							before_: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
						},
						...body?.flow_runs,
					},
				},
			})
			.then((response) => response.data);
		return response as number;
	},
});

export const deploymentsQueryParams = (
	id: string,
	body: components["schemas"]["Body_read_deployments_deployments_filter_post"],
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["deployments", string];
	queryFn: () => Promise<components["schemas"]["DeploymentResponse"][]>;
} => ({
	...queryParams,
	queryKey: ["deployments", JSON.stringify({ ...body, flowId: id })] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/deployments/filter", {
				body: {
					...body,
					flows: {
						...body?.flows,
						operator: "and_" as const,
						id: { any_: [id] },
					},
				},
			})
			.then((response) => response.data);
		return response as components["schemas"]["DeploymentResponse"][];
	},
});

export const deploymentsCountQueryParams = (
	id: string,
	queryParams: Partial<QueryObserverOptions> = {},
): {
	queryKey: readonly ["deploymentsCount", string];
	queryFn: () => Promise<number>;
} => ({
	...queryParams,
	queryKey: ["deploymentsCount", JSON.stringify({ flowId: id })] as const,
	queryFn: async () => {
		const response = await getQueryService()
			.POST("/deployments/count", {
				body: { flows: { operator: "and_" as const, id: { any_: [id] } } },
			})
			.then((response) => response.data);
		return response as number;
	},
});

export const deleteFlowMutation = (
	id: string,
): {
	mutationFn: MutationFunction<void>;
} => ({
	mutationFn: async () => {
		await getQueryService().DELETE("/flows/{id}", {
			params: { path: { id } },
		});
	},
});

// Define the Flow class
export class FlowQuery {
	private flowId: string;

	/**
	 * Initializes a new instance of the Flow class.
	 * @param flowId - The ID of the flow.
	 */
	constructor(flowId: string) {
		this.flowId = flowId;
	}

	public getQueryParams(queryParams: Partial<QueryObserverOptions> = {}): {
		queryKey: QueryKey;
		queryFn: QueryFunction<components["schemas"]["Flow"]>;
	} {
		return flowQueryParams(this.flowId, queryParams);
	}

	public getFlowRunsQueryParams(
		body: components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"],
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["flowRun", string];
		queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
	} {
		return flowRunsQueryParams(this.flowId, body, queryParams);
	}

	public getLatestFlowRunsQueryParams(
		n: number,
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["flowRun", string];
		queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
	} {
		return flowRunsQueryParams(
			this.flowId,
			{ offset: 0, limit: n, sort: "START_TIME_DESC" },
			queryParams,
		);
	}

	public getNextFlowRunsQueryParams(
		n: number,
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["flowRun", string];
		queryFn: () => Promise<components["schemas"]["FlowRunResponse"][]>;
	} {
		return flowRunsQueryParams(
			this.flowId,
			{
				offset: 0,
				limit: n,
				sort: "EXPECTED_START_TIME_ASC",
				flow_runs: {
					operator: "and_",
					expected_start_time: {
						after_: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
					},
				},
			},
			queryParams,
		);
	}

	public getFlowRunsCountQueryParams(
		body?: components["schemas"]["Body_count_flow_runs_flow_runs_count_post"],
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["flowRunCount", string];
		queryFn: () => Promise<number>;
	} {
		return flowRunsCountQueryParams(this.flowId, body, queryParams);
	}

	public getDeploymentsQueryParams(
		body: components["schemas"]["Body_read_deployments_deployments_filter_post"],
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["deployments", string];
		queryFn: () => Promise<components["schemas"]["DeploymentResponse"][]>;
	} {
		return deploymentsQueryParams(this.flowId, body, queryParams);
	}

	public getDeploymentsCountQueryParams(
		queryParams: Partial<QueryObserverOptions> = {},
	): {
		queryKey: readonly ["deploymentsCount", string];
		queryFn: () => Promise<number>;
	} {
		return deploymentsCountQueryParams(this.flowId, queryParams);
	}

	public getDeleteFlowMutation(): {
		mutationFn: MutationFunction<void>;
	} {
		return deleteFlowMutation(this.flowId);
	}
}
