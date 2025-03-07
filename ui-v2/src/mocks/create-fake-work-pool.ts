import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";
import { createFakeWorkPoolType } from "./create-fake-work-pool-type";
const STATUS_TYPE_VALUES = ["READY", "NOT_READY", "PAUSED"] as const;

export const createFakeWorkPool = (
	overrides?: Partial<components["schemas"]["WorkPool"]>,
): components["schemas"]["WorkPool"] => {
	return {
		created: faker.date.past().toISOString(),
		description: `${faker.word.adjective()} ${faker.word.noun()}`,
		id: faker.string.uuid(),
		name: `${faker.word.adjective()} work pool`,
		updated: faker.date.past().toISOString(),
		base_job_template: {},
		concurrency_limit: faker.number.int({ min: 0, max: 1_000 }),
		default_queue_id: faker.string.uuid(),
		is_paused: faker.datatype.boolean(),
		status: faker.helpers.arrayElement(STATUS_TYPE_VALUES),
		type: createFakeWorkPoolType(),
		...overrides,
	};
};
