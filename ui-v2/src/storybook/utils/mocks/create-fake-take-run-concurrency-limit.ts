import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeTaskRunConcurrencyLimit = (
	overrides?: Partial<components["schemas"]["ConcurrencyLimit"]>,
): components["schemas"]["ConcurrencyLimit"] => {
	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		tag: faker.vehicle.bicycle(),
		concurrency_limit: faker.number.int({ min: 0, max: 1000 }),
		active_slots: [faker.string.uuid()],
		...overrides,
	};
};
