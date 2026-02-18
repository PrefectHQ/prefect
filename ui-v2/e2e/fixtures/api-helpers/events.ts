import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Event = components["schemas"]["Event"];
export type ReceivedEvent = components["schemas"]["ReceivedEvent"];
export type EventPage = components["schemas"]["EventPage"];

export async function emitEvents(
	client: PrefectApiClient,
	events: Event[],
): Promise<void> {
	const { error } = await client.POST("/events", {
		body: events,
	});
	if (error) {
		throw new Error(`Failed to emit events: ${JSON.stringify(error)}`);
	}
}

export function buildTestEvent(params: {
	event: string;
	resourceId: string;
	resourceName?: string;
	payload?: Record<string, unknown>;
	related?: Array<Record<string, string>>;
}): Event {
	return {
		occurred: new Date().toISOString(),
		event: params.event,
		resource: {
			"prefect.resource.id": params.resourceId,
			...(params.resourceName
				? { "prefect.resource.name": params.resourceName }
				: {}),
		},
		related: params.related ?? [],
		payload: params.payload ?? {},
		id: crypto.randomUUID(),
	};
}

export async function listEvents(
	client: PrefectApiClient,
	filter?: {
		occurred?: { since?: string; until?: string };
		any_resource?: { id_prefix?: string[] };
		event?: { prefix?: string[] };
	},
): Promise<EventPage> {
	const { data, error } = await client.POST("/events/filter", {
		body: {
			filter: {
				occurred: filter?.occurred ?? {
					since: new Date(Date.now() - 86400000).toISOString(),
					until: new Date().toISOString(),
				},
				any_resource: filter?.any_resource,
				event: filter?.event,
				order: "DESC",
			},
			limit: 50,
		},
	});
	if (error) {
		throw new Error(`Failed to list events: ${JSON.stringify(error)}`);
	}
	if (!data) {
		throw new Error("No data returned from events filter");
	}
	return data;
}
