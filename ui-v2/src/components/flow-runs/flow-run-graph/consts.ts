import type { StateType } from "@prefecthq/graphs";

export const stateTypeColors: Record<StateType, string> = {
	COMPLETED: "#219D4B",
	RUNNING: "#09439B",
	SCHEDULED: "#E08504",
	PENDING: "#554B58",
	FAILED: "#DE0529",
	CANCELLED: "#333333",
	CANCELLING: "#333333",
	CRASHED: "#EA580C",
	PAUSED: "#554B58",
};
