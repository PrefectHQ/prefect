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

/**
 * Creates fake flow runs spanning multiple days for testing multi-day x-axis formatting.
 * Flow runs are distributed across the specified number of days.
 */
export const createFakeSimpleFlowRunsMultiDay = (
	count = 20,
	days = 3,
): SimpleFlowRun[] => {
	const now = new Date();
	const startTime = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

	return Array.from({ length: count }, (_, i) => {
		// Distribute flow runs evenly across the time range
		const progress = i / (count - 1);
		const timestamp = new Date(
			startTime.getTime() + progress * days * 24 * 60 * 60 * 1000,
		);

		return createFakeSimpleFlowRun({
			timestamp: timestamp.toISOString(),
		});
	});
};
