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

/**
 * State types that are considered "pending-like" — the run has not yet
 * produced execution data so graph / task-runs / subflow-runs / artifacts
 * UI should be hidden.
 *
 * Matches V1 behaviour where both SCHEDULED and PENDING are treated as
 * pending, with a special exception for "AwaitingRetry" (SCHEDULED) which
 * *does* have execution data from a prior failed attempt.
 */
const PENDING_LIKE_STATES: StateType[] = ["PENDING", "SCHEDULED"];

export function isPendingLikeState(
	stateType: StateType | null | undefined,
	stateName: string | null | undefined,
): boolean {
	if (stateType == null) {
		return true;
	}
	// AwaitingRetry is SCHEDULED but has execution data from the failed run
	if (stateName === "AwaitingRetry") {
		return false;
	}
	return PENDING_LIKE_STATES.includes(stateType);
}
