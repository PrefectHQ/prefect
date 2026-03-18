export const stateType = [
	"COMPLETED",
	"RUNNING",
	"SCHEDULED",
	"PENDING",
	"FAILED",
	"CANCELLED",
	"CANCELLING",
	"CRASHED",
	"PAUSED",
] as const;

export type StateType = (typeof stateType)[number];

export type RunGraphStateEvent = {
	id: string;
	timestamp: Date;
	type: StateType;
	name: string;
};
