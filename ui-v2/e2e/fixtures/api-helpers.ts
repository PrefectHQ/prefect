import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "./api-client";

export type Automation = components["schemas"]["Automation"];
export type Flow = components["schemas"]["Flow"];
export type Deployment = components["schemas"]["DeploymentResponse"];

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
