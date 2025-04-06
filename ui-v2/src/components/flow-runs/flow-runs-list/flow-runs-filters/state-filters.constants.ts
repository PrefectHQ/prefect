import type { components } from "@/api/prefect";

export const FLOW_RUN_STATES = [
	"Scheduled",
	"Late",
	"Resuming",
	"AwaitingRetry",
	"AwaitingConcurrencySlot",
	"Pending",
	"Paused",
	"Suspended",
	"Running",
	"Retrying",
	"Completed",
	"Cached",
	"Cancelled",
	"Cancelling",
	"Crashed",
	"Failed",
	"TimedOut",
] as const;
export type FlowRunState = (typeof FLOW_RUN_STATES)[number];
export const FLOW_RUN_STATES_NO_SCHEDULED = FLOW_RUN_STATES.filter(
	(flowStateFilter) => flowStateFilter !== "Scheduled",
);
export const FLOW_RUN_STATES_MAP = {
	Scheduled: "SCHEDULED",
	Late: "SCHEDULED",
	Resuming: "SCHEDULED",
	AwaitingRetry: "SCHEDULED",
	AwaitingConcurrencySlot: "SCHEDULED",
	Pending: "PENDING",
	Paused: "PAUSED",
	Suspended: "PAUSED",
	Running: "RUNNING",
	Retrying: "RUNNING",
	Completed: "COMPLETED",
	Cached: "COMPLETED",
	Cancelled: "CANCELLED",
	Cancelling: "CANCELLING",
	Crashed: "CRASHED",
	Failed: "FAILED",
	TimedOut: "FAILED",
} satisfies Record<FlowRunState, components["schemas"]["StateType"]>;
