import type { components } from "@/api/prefect";
import {
	randBoolean,
	randPastDate,
	randProductAdjective,
	randUuid,
} from "@ngneat/falso";

export const createFakeBlockType = (
	overrides?: Partial<components["schemas"]["BlockType"]>,
): components["schemas"]["BlockType"] => {
	return {
		created: randPastDate().toISOString(),
		id: randUuid(),
		is_protected: randBoolean(),
		name: `${randProductAdjective()} block type`,
		slug: `${randProductAdjective()} block`,
		updated: randPastDate().toISOString(),
		...overrides,
	};
};
