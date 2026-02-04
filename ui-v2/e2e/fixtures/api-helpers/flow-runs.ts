import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type FlowRun = components["schemas"]["FlowRun"];

export async function createFlowRun(
	client: PrefectApiClient,
	params: {
		flowId: string;
		deploymentId?: string;
		name?: string;
		state?: {
			type:
				| "COMPLETED"
				| "FAILED"
				| "CRASHED"
				| "RUNNING"
				| "PENDING"
				| "SCHEDULED"
				| "CANCELLED"
				| "CANCELLING"
				| "PAUSED";
			name?: string;
		};
		tags?: string[];
		parentTaskRunId?: string;
	},
): Promise<FlowRun> {
	const { data, error } = await client.POST("/flow_runs/", {
		body: {
			flow_id: params.flowId,
			deployment_id: params.deploymentId,
			name: params.name ?? `e2e-flow-run-${Date.now()}`,
			state: params.state ?? { type: "COMPLETED", name: "Completed" },
			tags: params.tags ?? [],
			parent_task_run_id: params.parentTaskRunId,
		},
	});
	if (error) {
		throw new Error(`Failed to create flow run: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listFlowRuns(
	client: PrefectApiClient,
): Promise<FlowRun[]> {
	const { data, error } = await client.POST("/flow_runs/filter", {
		body: {
			sort: "START_TIME_DESC",
			limit: 100,
		},
	});
	if (error) {
		throw new Error(`Failed to list flow runs: ${JSON.stringify(error)}`);
	}
	return data ?? [];
}

export async function deleteFlowRun(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/flow_runs/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete flow run: ${JSON.stringify(error)}`);
	}
}

export async function cleanupFlowRuns(
	client: PrefectApiClient,
	prefix: string,
): Promise<void> {
	const flowRuns = await listFlowRuns(client);
	const toDelete = flowRuns.filter((fr) => fr.name?.startsWith(prefix));
	await Promise.all(toDelete.map((fr) => deleteFlowRun(client, fr.id)));
}
