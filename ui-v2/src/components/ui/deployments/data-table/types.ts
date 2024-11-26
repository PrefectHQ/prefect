import type { components } from "@/api/prefect";

export type DeploymentWithFlowName =
	components["schemas"]["DeploymentResponse"] & {
		flowName: string;
	};
