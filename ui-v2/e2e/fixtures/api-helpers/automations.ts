import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Automation = components["schemas"]["Automation"];

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
