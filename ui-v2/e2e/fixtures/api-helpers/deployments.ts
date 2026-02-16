import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Deployment = components["schemas"]["DeploymentResponse"];

export async function createDeployment(
	client: PrefectApiClient,
	params: {
		name: string;
		flowId: string;
		tags?: string[];
		description?: string;
		paused?: boolean;
		workPoolName?: string;
		workQueueName?: string;
		schedules?: Array<{
			active: boolean;
			schedule: { interval: number } | { cron: string } | { rrule: string };
		}>;
	},
): Promise<Deployment> {
	const { data, error } = await client.POST("/deployments/", {
		body: {
			name: params.name,
			flow_id: params.flowId,
			tags: params.tags,
			description: params.description,
			paused: params.paused ?? false,
			enforce_parameter_schema: true,
			work_pool_name: params.workPoolName,
			work_queue_name: params.workQueueName,
			schedules: params.schedules,
		},
	});
	if (error) {
		throw new Error(`Failed to create deployment: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listDeployments(
	client: PrefectApiClient,
): Promise<Deployment[]> {
	const { data, error } = await client.POST("/deployments/filter", {
		body: {
			sort: "NAME_ASC",
			limit: 100,
			offset: 0,
		},
	});
	if (error) {
		throw new Error(`Failed to list deployments: ${JSON.stringify(error)}`);
	}
	return data ?? [];
}

export async function deleteDeployment(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/deployments/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete deployment: ${JSON.stringify(error)}`);
	}
}

export async function cleanupDeployments(
	client: PrefectApiClient,
	prefix: string,
): Promise<void> {
	const deployments = await listDeployments(client);
	const toDelete = deployments.filter((d) => d.name.startsWith(prefix));
	await Promise.all(
		toDelete.map((d) => deleteDeployment(client, d.id).catch(() => {})),
	);
}
