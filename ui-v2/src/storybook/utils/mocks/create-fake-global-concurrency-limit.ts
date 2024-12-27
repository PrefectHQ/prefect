import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeGlobalConcurrencyLimit = (
	overrides?: Partial<components["schemas"]["GlobalConcurrencyLimitResponse"]>,
): components["schemas"]["GlobalConcurrencyLimitResponse"] => {
	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		active: faker.datatype.boolean(),
		name: faker.word.noun(),
		limit: faker.number.int({ min: 0, max: 1000 }),
		active_slots: faker.number.int({ min: 0, max: 1000 }),
		slot_decay_per_second: faker.number.int({ min: 0, max: 1000 }),

		...overrides,
	};
};
