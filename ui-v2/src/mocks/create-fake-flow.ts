import {
	randNumber,
	randPastDate,
	randProductName,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeFlow = (
	overrides?: Partial<components["schemas"]["Flow"]>,
): components["schemas"]["Flow"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: randProductName(),
		tags: randWord({ length: randNumber({ min: 0, max: 6 }) }),
		labels: {},
		...overrides,
	};
};
