import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeArtifact = (
	overrides?: Partial<components["schemas"]["Artifact"]>,
): components["schemas"]["Artifact"] => {
	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		key: `key-${faker.string.alphanumeric({ length: 10 })}`,
		type: "result",
		description: faker.lorem.sentence(),
		data: {
			arr: faker.helpers.uniqueArray([faker.word.sample()], 5),
		},
		metadata_: {
			key: faker.lorem.word(),
			[faker.lorem.word()]: faker.lorem.word(),
		},
		flow_run_id: faker.string.uuid(),
		task_run_id: faker.string.uuid(),
		...overrides,
	};
};
