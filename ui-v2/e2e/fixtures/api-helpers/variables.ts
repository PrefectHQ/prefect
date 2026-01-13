import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Variable = components["schemas"]["Variable"];

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
