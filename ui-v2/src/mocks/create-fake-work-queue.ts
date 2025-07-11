import {
	randBoolean,
	randNumber,
	randPastDate,
	randProductAdjective,
	randProductName,
	randUuid,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeWorkQueue = (
	overrides?: Partial<components["schemas"]["WorkQueueResponse"]>,
): components["schemas"]["WorkQueueResponse"] => {
	return {
		created: randPastDate().toISOString(),
		description: `${randProductAdjective()} ${randProductName()}`,
		id: randUuid(),
		name: `${randProductAdjective()} work queue`,
		updated: randPastDate().toISOString(),
		concurrency_limit: randNumber({ min: 0, max: 1_000 }),
		is_paused: randBoolean(),
		last_polled: randPastDate().toISOString(),
		work_pool_id: randUuid(),
		work_pool_name: `${randProductAdjective()} work pool`,
		priority: randNumber({ min: 1, max: 5 }),
		...overrides,
	};
};
