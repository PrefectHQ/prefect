import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeBlockDocument = (
	overrides?: Partial<components["schemas"]["BlockDocument"]>,
): components["schemas"]["BlockDocument"] => {
	return {
		block_schema_id: faker.string.uuid(),
		block_type_id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		id: faker.string.uuid(),
		is_anonymous: faker.datatype.boolean(),
		name: `${faker.word.adjective()} block`,
		updated: faker.date.past().toISOString(),
		...overrides,
	};
};
