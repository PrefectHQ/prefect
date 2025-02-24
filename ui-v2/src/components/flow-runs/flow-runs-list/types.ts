import { Deployment } from "@/api/deployments";
import { FlowRun } from "@/api/flow-runs";
import { Flow } from "@/api/flows";

export type FlowRunRow = FlowRun & {
	flow: Flow;
	deployment?: Deployment;
};
