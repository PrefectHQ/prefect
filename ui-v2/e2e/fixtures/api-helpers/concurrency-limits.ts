import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type GlobalConcurrencyLimit =
	components["schemas"]["GlobalConcurrencyLimitResponse"];
export type TaskRunConcurrencyLimit = components["schemas"]["ConcurrencyLimit"];

export async function listGlobalConcurrencyLimits(
	client: PrefectApiClient,
): Promise<GlobalConcurrencyLimit[]> {
	const { data, error } = await client.POST("/v2/concurrency_limits/filter", {
		body: {},
	});
	if (error) {
		throw new Error(
			`Failed to list global concurrency limits: ${JSON.stringify(error)}`,
		);
	}
	return data ?? [];
}

export async function createGlobalConcurrencyLimit(
	client: PrefectApiClient,
	params: {
		name: string;
		limit: number;
		slot_decay_per_second?: number;
		active?: boolean;
	},
): Promise<GlobalConcurrencyLimit> {
	const { data, error } = await client.POST("/v2/concurrency_limits/", {
		body: {
			name: params.name,
			limit: params.limit,
			slot_decay_per_second: params.slot_decay_per_second ?? 0,
			active: params.active ?? true,
		},
	});
	if (error) {
		throw new Error(
			`Failed to create global concurrency limit: ${JSON.stringify(error)}`,
		);
	}
	return data;
}

export async function deleteGlobalConcurrencyLimit(
	client: PrefectApiClient,
	idOrName: string,
): Promise<void> {
	const { error } = await client.DELETE("/v2/concurrency_limits/{id_or_name}", {
		params: { path: { id_or_name: idOrName } },
	});
	if (error) {
		throw new Error(
			`Failed to delete global concurrency limit: ${JSON.stringify(error)}`,
		);
	}
}

export async function cleanupGlobalConcurrencyLimits(
	client: PrefectApiClient,
	namePrefix: string,
): Promise<void> {
	const limits = await listGlobalConcurrencyLimits(client);
	const toDelete = limits.filter((l) => l.name.startsWith(namePrefix));
	await Promise.all(
		toDelete.map((l) => deleteGlobalConcurrencyLimit(client, l.id)),
	);
}

export async function listTaskRunConcurrencyLimits(
	client: PrefectApiClient,
): Promise<TaskRunConcurrencyLimit[]> {
	const { data, error } = await client.POST("/concurrency_limits/filter", {
		body: {},
	});
	if (error) {
		throw new Error(
			`Failed to list task run concurrency limits: ${JSON.stringify(error)}`,
		);
	}
	return data ?? [];
}

export async function createTaskRunConcurrencyLimit(
	client: PrefectApiClient,
	params: { tag: string; concurrency_limit: number },
): Promise<TaskRunConcurrencyLimit> {
	const { data, error } = await client.POST("/concurrency_limits/", {
		body: { tag: params.tag, concurrency_limit: params.concurrency_limit },
	});
	if (error) {
		throw new Error(
			`Failed to create task run concurrency limit: ${JSON.stringify(error)}`,
		);
	}
	return data;
}

export async function deleteTaskRunConcurrencyLimit(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/concurrency_limits/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(
			`Failed to delete task run concurrency limit: ${JSON.stringify(error)}`,
		);
	}
}

export async function cleanupTaskRunConcurrencyLimits(
	client: PrefectApiClient,
	tagPrefix: string,
): Promise<void> {
	const limits = await listTaskRunConcurrencyLimits(client);
	const toDelete = limits.filter((l) => l.tag.startsWith(tagPrefix));
	await Promise.all(
		toDelete.map((l) => deleteTaskRunConcurrencyLimit(client, l.id)),
	);
}
