import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Deployment = components["schemas"]["DeploymentResponse"];

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
