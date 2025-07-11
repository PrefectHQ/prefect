import {
	randBoolean,
	randPastDate,
	randProductAdjective,
	randUuid,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeBlockDocument = (
	overrides?: Partial<components["schemas"]["BlockDocument"]>,
): components["schemas"]["BlockDocument"] => {
	return {
		block_schema_id: randUuid(),
		block_type_id: randUuid(),
		created: randPastDate().toISOString(),
		id: randUuid(),
		is_anonymous: randBoolean(),
		name: `${randProductAdjective()} block`,
		updated: randPastDate().toISOString(),
		...overrides,
	};
};
