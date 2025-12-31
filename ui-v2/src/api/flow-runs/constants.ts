import type { components } from "@/api/prefect";

export const RUN_STATES = {
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

export type RunStates = keyof typeof RUN_STATES;

export type StateType = components["schemas"]["StateType"];

/**
 * All possible state names that can be used in automations.
 * This list is intentionally ordered by state type progression
 * to match the Vue implementation.
 */
export const STATE_NAMES = [
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

export type StateName = (typeof STATE_NAMES)[number];

/**
 * Maps state names to their corresponding state types.
 * Multiple state names can map to the same state type.
 */
export const STATE_NAME_TO_TYPE: Record<StateName, StateType> = {
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
} as const;

/**
 * State names that are not "Scheduled" - used for the "All except scheduled" convenience option.
 */
export const STATE_NAMES_WITHOUT_SCHEDULED = STATE_NAMES.filter(
	(name) => name !== "Scheduled",
);
