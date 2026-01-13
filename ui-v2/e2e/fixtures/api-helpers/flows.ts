import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Flow = components["schemas"]["Flow"];

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
