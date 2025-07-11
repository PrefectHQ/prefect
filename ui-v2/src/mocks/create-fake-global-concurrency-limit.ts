import {
	randBoolean,
	randNumber,
	randPastDate,
	randProductName,
	randUuid,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeGlobalConcurrencyLimit = (
	overrides?: Partial<components["schemas"]["GlobalConcurrencyLimitResponse"]>,
): components["schemas"]["GlobalConcurrencyLimitResponse"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		active: randBoolean(),
		name: randProductName(),
		limit: randNumber({ min: 0, max: 1000 }),
		active_slots: randNumber({ min: 0, max: 1000 }),
		slot_decay_per_second: randNumber({ min: 0, max: 1000 }),

		...overrides,
	};
};
