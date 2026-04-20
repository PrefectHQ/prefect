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
	options?: { ignoreNotFound?: boolean },
): Promise<void> {
	const { error } = await client.DELETE("/variables/{id}", {
		params: { path: { id } },
	});
	if (error) {
		// Ignore "not found" errors during cleanup when running parallel tests
		// since another test might have already deleted the variable
		const isNotFound =
			typeof error === "object" &&
			error !== null &&
			"detail" in error &&
			String(error.detail).includes("not found");
		if (options?.ignoreNotFound && isNotFound) {
			return;
		}
		throw new Error(`Failed to delete variable: ${JSON.stringify(error)}`);
	}
}

export async function cleanupVariables(
	client: PrefectApiClient,
	namePrefix: string,
): Promise<void> {
	const variables = await listVariables(client);
	const toDelete = variables.filter((v) => v.name.startsWith(namePrefix));
	// Use ignoreNotFound to handle race conditions when parallel tests
	// try to delete the same variables
	await Promise.all(
		toDelete.map((v) => deleteVariable(client, v.id, { ignoreNotFound: true })),
	);
}
