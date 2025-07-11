import {
	randBoolean,
	randPastDate,
	randProductAdjective,
	randProductName,
	randUuid,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeAutomation = (
	overrides?: Partial<components["schemas"]["Automation"]>,
): components["schemas"]["Automation"] => {
	return {
		name: `${randProductAdjective()} automation`,
		description: `${randProductAdjective()} ${randProductName()}`,
		enabled: randBoolean(),
		trigger: {
			type: "event",
			id: randUuid(),
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
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		...overrides,
	};
};
