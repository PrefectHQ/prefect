import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "./api-client";

export type Automation = components["schemas"]["Automation"];
export type Flow = components["schemas"]["Flow"];
export type Deployment = components["schemas"]["DeploymentResponse"];
export type GlobalConcurrencyLimit =
	components["schemas"]["GlobalConcurrencyLimitResponse"];
export type TaskRunConcurrencyLimit = components["schemas"]["ConcurrencyLimit"];
export type Variable = components["schemas"]["Variable"];

export async function waitForServerHealth(
	client: PrefectApiClient,
	timeoutMs = 30000,
): Promise<void> {
	const startTime = Date.now();
	while (Date.now() - startTime < timeoutMs) {
		const { response } = await client.GET("/health");
		if (response.ok) {
			return;
		}
		await new Promise((resolve) => setTimeout(resolve, 500));
	}
	throw new Error(`Server did not become healthy within ${timeoutMs}ms`);
}

export async function createFlow(
	client: PrefectApiClient,
	name: string,
): Promise<Flow> {
	const { data, error } = await client.POST("/flows/", {
		body: { name },
	});
	if (error) {
		throw new Error(`Failed to create flow: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function createDeployment(
	client: PrefectApiClient,
	params: { name: string; flowId: string },
): Promise<Deployment> {
	const { data, error } = await client.POST("/deployments/", {
		body: {
			name: params.name,
			flow_id: params.flowId,
		},
	});
	if (error) {
		throw new Error(`Failed to create deployment: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listAutomations(
	client: PrefectApiClient,
): Promise<Automation[]> {
	const { data, error } = await client.POST("/automations/filter", {
		body: {},
	});
	if (error) {
		throw new Error(`Failed to list automations: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function deleteAutomation(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/automations/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete automation: ${JSON.stringify(error)}`);
	}
}

export async function cleanupAutomations(
	client: PrefectApiClient,
	namePrefix: string,
): Promise<void> {
	const automations = await listAutomations(client);
	const toDelete = automations.filter((a) => a.name.startsWith(namePrefix));
	await Promise.all(toDelete.map((a) => deleteAutomation(client, a.id)));
}

export async function listVariables(
	client: PrefectApiClient,
): Promise<Variable[]> {
	const { data, error } = await client.POST("/variables/filter", {
		body: {},
	});
	if (error) {
		throw new Error(`Failed to list variables: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function createVariable(
	client: PrefectApiClient,
	params: { name: string; value: unknown; tags?: string[] },
): Promise<Variable> {
	const { data, error } = await client.POST("/variables/", {
		body: {
			name: params.name,
			value: params.value,
			tags: params.tags,
		},
	});
	if (error) {
		throw new Error(`Failed to create variable: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function deleteVariable(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/variables/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete variable: ${JSON.stringify(error)}`);
	}
}

export async function cleanupVariables(
	client: PrefectApiClient,
	namePrefix: string,
): Promise<void> {
	const variables = await listVariables(client);
	const toDelete = variables.filter((v) => v.name.startsWith(namePrefix));
	await Promise.all(toDelete.map((v) => deleteVariable(client, v.id)));
}

// Global Concurrency Limits
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

// Task Run Concurrency Limits
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
