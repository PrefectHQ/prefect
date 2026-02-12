import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Flow = components["schemas"]["Flow"];

export async function createFlow(
	client: PrefectApiClient,
	nameOrParams: string | { name: string; tags?: string[] },
): Promise<Flow> {
	const params =
		typeof nameOrParams === "string" ? { name: nameOrParams } : nameOrParams;
	const { data, error } = await client.POST("/flows/", {
		body: { name: params.name, tags: params.tags },
	});
	if (error) {
		throw new Error(`Failed to create flow: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listFlows(client: PrefectApiClient): Promise<Flow[]> {
	const { data, error } = await client.POST("/flows/filter", {
		body: {
			sort: "NAME_ASC",
			limit: 100,
		},
	});
	if (error) {
		throw new Error(`Failed to list flows: ${JSON.stringify(error)}`);
	}
	return data ?? [];
}

export async function deleteFlow(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/flows/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete flow: ${JSON.stringify(error)}`);
	}
}

export async function cleanupFlows(
	client: PrefectApiClient,
	prefix: string,
): Promise<void> {
	const flows = await listFlows(client);
	const toDelete = flows.filter((f) => f.name.startsWith(prefix));
	await Promise.all(
		toDelete.map((f) => deleteFlow(client, f.id).catch(() => {})),
	);
}
