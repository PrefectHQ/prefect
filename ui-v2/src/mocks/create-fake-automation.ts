import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

export const createFakeAutomation = (
	overrides?: Partial<components["schemas"]["Automation"]>,
): components["schemas"]["Automation"] => {
	return {
		name: `${faker.word.adjective()} automation`,
		description: `${faker.word.adjective()} ${faker.word.noun()}`,
		enabled: faker.datatype.boolean(),
		trigger: {
			type: "event",
			id: faker.string.uuid(),
			match: {
				"prefect.resource.id": "prefect.deployment.*",
			},
			match_related: {},
			after: [],
			expect: ["prefect.deployment.not-ready"],
			for_each: ["prefect.resource.id"],
			posture: "Reactive",
			threshold: 1,
			within: 0,
		},
		actions: [
			{
				type: "cancel-flow-run",
			},
		],
		actions_on_trigger: [],
		actions_on_resolve: [],
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		...overrides,
	};
};
