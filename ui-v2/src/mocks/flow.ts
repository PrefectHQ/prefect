import {
	randAlphaNumeric,
	randPastDate,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { Flow } from "@/api/flows";

export const createMockFlow = (overrides?: Partial<Flow>): Flow => ({
	id: randUuid(),
	created: randPastDate().toISOString(),
	updated: randPastDate().toISOString(),
	name: `${randWord()}-${randAlphaNumeric({ length: 6 }).join("").toLowerCase()}`,
	tags: [],
	labels: {},
	...overrides,
});
