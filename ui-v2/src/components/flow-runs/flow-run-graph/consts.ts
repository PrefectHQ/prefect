import type { StateType } from "@prefecthq/graphs";

export const stateTypeColors: Record<StateType, string> = {
	COMPLETED: "var(--state-completed-600)",
	RUNNING: "var(--state-running-700)",
	SCHEDULED: "var(--state-scheduled-700)",
	PENDING: "var(--state-pending-800)",
	FAILED: "var(--state-failed-700)",
	CANCELLED: "var(--state-cancelled-600)",
	CANCELLING: "var(--state-cancelling-600)",
	CRASHED: "var(--state-crashed-600)",
	PAUSED: "var(--state-paused-800)",
};
