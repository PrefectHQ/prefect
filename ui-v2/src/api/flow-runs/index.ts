import { Deployment } from "../deployments";
import { Flow } from "../flows";
import { components } from "../prefect";

export type FlowRun = components["schemas"]["FlowRun"];
export type FlowRunWithDeploymentAndFlow = FlowRun & {
	deployment: Deployment;
	flow: Flow;
};
