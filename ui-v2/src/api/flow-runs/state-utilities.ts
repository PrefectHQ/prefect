import type { components } from "@/api/prefect";

type StateType = components["schemas"]["StateType"];

/**
 * States that can be cancelled - flow runs that are "stuck" or in-progress
 */
export const STUCK_STATES: StateType[] = [
	"RUNNING",
	"SCHEDULED",
	"PENDING",
	"PAUSED",
];

/**
 * States that are terminal - flow runs that have completed execution
 */
export const TERMINAL_STATES: StateType[] = [
	"COMPLETED",
	"FAILED",
	"CANCELLED",
	"CRASHED",
];

/**
 * Check if a flow run can be cancelled (is in a stuck/cancellable state)
 */
export function isStuckState(stateType: StateType | null | undefined): boolean {
	return stateType != null && STUCK_STATES.includes(stateType);
}

/**
 * Check if a flow run can be paused (is currently running)
 */
export function isRunningState(
	stateType: StateType | null | undefined,
): boolean {
	return stateType === "RUNNING";
}

/**
 * Check if a flow run can be resumed (is currently paused)
 */
export function isPausedState(
	stateType: StateType | null | undefined,
): boolean {
	return stateType === "PAUSED";
}

/**
 * Check if a flow run is in a terminal state
 */
export function isTerminalState(
	stateType: StateType | null | undefined,
): boolean {
	return stateType != null && TERMINAL_STATES.includes(stateType);
}
