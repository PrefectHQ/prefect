import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeWorkQueue = (
	overrides?: Partial<components["schemas"]["WorkQueueResponse"]>,
): components["schemas"]["WorkQueueResponse"] => {
	return {
		created: faker.date.past().toISOString(),
		description: `${faker.word.adjective()} ${faker.word.noun()}`,
		id: faker.string.uuid(),
		name: `${faker.word.adjective()} work queue`,
		updated: faker.date.past().toISOString(),
		concurrency_limit: faker.number.int({ min: 0, max: 1_000 }),
		is_paused: faker.datatype.boolean(),
		last_polled: faker.date.past().toISOString(),
		work_pool_id: `${faker.word.adjective()} work queue`,
		work_pool_name: `${faker.word.adjective()} work pool`,
		priority: faker.number.int({ min: 1, max: 5 }),
		...overrides,
	};
};
