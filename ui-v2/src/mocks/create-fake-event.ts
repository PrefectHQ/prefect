import { randPastDate, randUuid } from "@ngneat/falso";
import type { components } from "@/api/prefect";

type Event = components["schemas"]["ReceivedEvent"];

export const createFakeEvent = (overrides?: Partial<Event>): Event => {
	return {
		id: randUuid(),
		occurred: randPastDate().toISOString(),
		event: "prefect.flow-run.Completed",
		resource: {
			"prefect.resource.id": `prefect.flow-run.${randUuid()}`,
			"prefect.resource.name": "my-flow-run",
		},
		related: [],
		payload: {},
		received: randPastDate().toISOString(),
		follows: null,
		...overrides,
	};
};
