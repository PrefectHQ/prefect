import { rand, randNumber, randPastDate, randUuid } from "@ngneat/falso";
import type { SimpleFlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";

type StateType = components["schemas"]["StateType"];

const STATE_TYPE_VALUES = [
	"COMPLETED",
	"FAILED",
	"CRASHED",
	"CANCELLED",
	"RUNNING",
	"PENDING",
	"SCHEDULED",
	"PAUSED",
	"CANCELLING",
] as const satisfies readonly StateType[];

export const createFakeSimpleFlowRun = (
	overrides?: Partial<SimpleFlowRun>,
): SimpleFlowRun => {
	return {
		id: randUuid(),
		state_type: rand(STATE_TYPE_VALUES),
		timestamp: randPastDate({ years: 0.1 }).toISOString(),
		duration: randNumber({ min: 1, max: 3600 }),
		lateness: randNumber({ min: 0, max: 300 }),
		...overrides,
	};
};

export const createFakeSimpleFlowRuns = (count = 10): SimpleFlowRun[] => {
	return Array.from({ length: count }, () => createFakeSimpleFlowRun());
};
