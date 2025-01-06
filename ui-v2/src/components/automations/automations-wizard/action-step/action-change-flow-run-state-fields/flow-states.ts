import { components } from "@/api/prefect";

export const FLOW_STATES = {
	COMPLETED: "Completed",
	RUNNING: "Running",
	SCHEDULED: "Scheduled",
	PENDING: "Pending",
	FAILED: "Failed",
	CANCELLED: "Cancelled",
	CANCELLING: "Cancelling",
	CRASHED: "Crashed",
	PAUSED: "Paused",
} as const satisfies Record<
	components["schemas"]["StateType"],
	Capitalize<Lowercase<components["schemas"]["StateType"]>>
>;
export type FlowStates = keyof typeof FLOW_STATES;
