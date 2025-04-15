import type { components } from "@/api/prefect";
import {
	rand,
	randBoolean,
	randNumber,
	randPastDate,
	randProductAdjective,
	randProductName,
	randUuid,
} from "@ngneat/falso";
import { createFakeWorkPoolType } from "./create-fake-work-pool-type";
const STATUS_TYPE_VALUES = ["READY", "NOT_READY", "PAUSED", null] as const;

export const createFakeWorkPool = (
	overrides?: Partial<components["schemas"]["WorkPool"]>,
): components["schemas"]["WorkPool"] => {
	return {
		created: randPastDate().toISOString(),
		description: `${randProductAdjective()} ${randProductName()}`,
		id: randUuid(),
		name: `${randProductAdjective()} work pool`,
		updated: randPastDate().toISOString(),
		base_job_template: {},
		concurrency_limit: randNumber({ min: 0, max: 1_000 }),
		default_queue_id: randUuid(),
		is_paused: randBoolean(),
		status: rand(STATUS_TYPE_VALUES),
		type: createFakeWorkPoolType(),
		...overrides,
	};
};
