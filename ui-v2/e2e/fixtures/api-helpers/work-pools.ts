import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type WorkPool = components["schemas"]["WorkPool"];
export type WorkPoolQueue = components["schemas"]["WorkQueueResponse"];

export async function createWorkPool(
	client: PrefectApiClient,
	params: {
		name: string;
		type?: string;
		description?: string;
		isPaused?: boolean;
	},
): Promise<WorkPool> {
	const { data, error } = await client.POST("/work_pools/", {
		body: {
			name: params.name,
			type: params.type ?? "process",
			description: params.description,
			is_paused: params.isPaused ?? false,
		},
	});
	if (error) {
		throw new Error(`Failed to create work pool: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function getWorkPool(
	client: PrefectApiClient,
	name: string,
): Promise<WorkPool> {
	const { data, error } = await client.GET("/work_pools/{name}", {
		params: { path: { name } },
	});
	if (error) {
		throw new Error(`Failed to get work pool: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listWorkPools(
	client: PrefectApiClient,
): Promise<WorkPool[]> {
	const { data, error } = await client.POST("/work_pools/filter", {
		body: {
			limit: 100,
			offset: 0,
		},
	});
	if (error) {
		throw new Error(`Failed to list work pools: ${JSON.stringify(error)}`);
	}
	return data ?? [];
}

export async function deleteWorkPool(
	client: PrefectApiClient,
	name: string,
): Promise<void> {
	const { error } = await client.DELETE("/work_pools/{name}", {
		params: { path: { name } },
	});
	if (error) {
		throw new Error(`Failed to delete work pool: ${JSON.stringify(error)}`);
	}
}

export async function cleanupWorkPools(
	client: PrefectApiClient,
	prefix: string,
): Promise<void> {
	const pools = await listWorkPools(client);
	const toDelete = pools.filter((p) => p.name.startsWith(prefix));
	await Promise.all(
		toDelete.map((p) => deleteWorkPool(client, p.name).catch(() => {})),
	);
}

export async function listWorkPoolQueues(
	client: PrefectApiClient,
	workPoolName: string,
): Promise<WorkPoolQueue[]> {
	const { data, error } = await client.POST(
		"/work_pools/{work_pool_name}/queues/filter",
		{
			params: { path: { work_pool_name: workPoolName } },
			body: {
				offset: 0,
			},
		},
	);
	if (error) {
		throw new Error(
			`Failed to list work pool queues: ${JSON.stringify(error)}`,
		);
	}
	return data ?? [];
}
