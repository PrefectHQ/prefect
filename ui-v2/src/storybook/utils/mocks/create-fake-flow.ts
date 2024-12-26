import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeFlow = (
	overrides?: Partial<components["schemas"]["Flow"]>,
): components["schemas"]["Flow"] => {
	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		name: faker.word.noun(),
		tags: [...faker.word.words({ count: { min: 0, max: 6 } })],
		labels: {},
		...overrides,
	};
};
