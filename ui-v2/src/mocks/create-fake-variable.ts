import {
	randPastDate,
	randProductAdjective,
	randProductName,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeVariable = (
	overrides?: Partial<components["schemas"]["Variable"]>,
): components["schemas"]["Variable"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: `${randProductAdjective()}_${randWord()}`.toLowerCase(),
		value: randProductName(),
		tags: [],
		...overrides,
	};
};
