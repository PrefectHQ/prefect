import {
	randNumber,
	randPastDate,
	randProductAdjective,
	randUuid,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeTaskRunConcurrencyLimit = (
	overrides?: Partial<components["schemas"]["ConcurrencyLimit"]>,
): components["schemas"]["ConcurrencyLimit"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		tag: randProductAdjective(),
		concurrency_limit: randNumber({ min: 0, max: 1000 }),
		active_slots: [randUuid()],
		...overrides,
	};
};
