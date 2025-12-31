import type { Event } from "@/api/events";
import type { EventTriggerInput, TriggerTemplate } from "./automation-schema";

/**
 * Known Prefect event prefixes used to identify resource types from event names.
 * These prefixes help determine the resource role (e.g., "flow-run", "work-queue")
 * from event strings like "prefect.flow-run.Completed".
 */
const PREFECT_EVENT_PREFIXES = [
	"prefect.block-document",
	"prefect.deployment",
	"prefect.flow-run",
	"prefect.flow",
	"prefect.task-run",
	"prefect.work-queue",
	"prefect.work-pool",
	"prefect.tag",
	"prefect.concurrency-limit",
	"prefect.artifact-collection",
	"prefect.automation",
] as const;

type PrefectResourceRole =
	| "block-document"
	| "deployment"
	| "flow-run"
	| "flow"
	| "task-run"
	| "work-queue"
	| "work-pool"
	| "tag"
	| "concurrency-limit"
	| "artifact-collection"
	| "automation";

/**
 * Extracts the Prefect resource role from an event type string.
 *
 * @param eventType - The event type string (e.g., "prefect.flow-run.Completed")
 * @returns The resource role (e.g., "flow-run") or null if not a known Prefect event
 *
 * @example
 * getPrefectResourceRole("prefect.flow-run.Completed") // returns "flow-run"
 * getPrefectResourceRole("prefect.work-queue.ready") // returns "work-queue"
 * getPrefectResourceRole("custom.event") // returns null
 */
export function getPrefectResourceRole(
	eventType: string,
): PrefectResourceRole | null {
	const roleRegex = new RegExp(
		`^(${PREFECT_EVENT_PREFIXES.join("|")})\\.`,
		"g",
	);
	const match = roleRegex.exec(eventType);
	if (!match) {
		return null;
	}

	const prefix = match[1];
	const role = prefix?.split(".").at(-1);

	if (role && isPrefectResourceRole(role)) {
		return role;
	}

	return null;
}

function isPrefectResourceRole(value: string): value is PrefectResourceRole {
	const validRoles: PrefectResourceRole[] = [
		"block-document",
		"deployment",
		"flow-run",
		"flow",
		"task-run",
		"work-queue",
		"work-pool",
		"tag",
		"concurrency-limit",
		"artifact-collection",
		"automation",
	];
	return validRoles.includes(value as PrefectResourceRole);
}

/**
 * Type for a related resource from an event.
 */
type RelatedResource = NonNullable<Event["related"]>[number];

/**
 * Finds a related resource by its role from an event's related resources array.
 *
 * @param related - Array of related resources from the event
 * @param role - The role to search for (e.g., "flow", "work-queue")
 * @returns The related resource with the matching role, or undefined if not found
 */
function getRelatedByRole(
	related: Event["related"],
	role: string,
): RelatedResource | undefined {
	if (!related) {
		return undefined;
	}
	return related.find((r) => r["prefect.resource.role"] === role);
}

/**
 * Result of transforming an event to automation wizard default values.
 */
export type EventToTriggerResult = {
	trigger: EventTriggerInput;
	triggerTemplate: TriggerTemplate;
};

/**
 * Transforms an Event into default values for the automation wizard.
 *
 * This function creates a trigger configuration based on the event type:
 * - For flow-run events: includes match_related for the associated flow
 * - For work-queue events: includes match_related for the work-queue
 * - For other events: creates a basic custom trigger
 *
 * All triggers use:
 * - posture: "Reactive"
 * - match: { "prefect.resource.id": <event's resource id> }
 * - for_each: ["prefect.resource.id"]
 * - expect: [<event type>]
 * - triggerTemplate: "custom"
 *
 * @param event - The event to transform
 * @returns An object containing the trigger configuration and template type
 *
 * @example
 * const event = {
 *   event: "prefect.flow-run.Completed",
 *   resource: { "prefect.resource.id": "prefect.flow-run.abc123" },
 *   related: [{ "prefect.resource.role": "flow", "prefect.resource.id": "prefect.flow.xyz789" }]
 * };
 * const result = transformEventToTrigger(event);
 * // result.trigger.match_related = { "prefect.resource.role": "flow", "prefect.resource.id": "prefect.flow.xyz789" }
 */
export function transformEventToTrigger(event: Event): EventToTriggerResult {
	const role = getPrefectResourceRole(event.event);

	switch (role) {
		case "flow-run":
			return createFlowRunTrigger(event);
		case "work-queue":
			return createWorkQueueTrigger(event);
		default:
			return createCustomTrigger(event);
	}
}

/**
 * Creates a trigger for flow-run events with match_related for the associated flow.
 */
function createFlowRunTrigger(event: Event): EventToTriggerResult {
	const relatedFlow = getRelatedByRole(event.related, "flow");

	const trigger: EventTriggerInput = {
		type: "event",
		match: {
			"prefect.resource.id": event.resource["prefect.resource.id"],
		},
		match_related: relatedFlow
			? {
					"prefect.resource.role": "flow",
					"prefect.resource.id": relatedFlow["prefect.resource.id"],
				}
			: {},
		after: [],
		expect: [event.event],
		for_each: ["prefect.resource.id"],
		posture: "Reactive",
		threshold: 1,
		within: 0,
	};

	return {
		trigger,
		triggerTemplate: "custom",
	};
}

/**
 * Creates a trigger for work-queue events with match_related for the work-queue.
 */
function createWorkQueueTrigger(event: Event): EventToTriggerResult {
	const relatedWorkQueue = getRelatedByRole(event.related, "work-queue");

	const trigger: EventTriggerInput = {
		type: "event",
		match: {
			"prefect.resource.id": event.resource["prefect.resource.id"],
		},
		match_related: relatedWorkQueue
			? {
					"prefect.resource.role": "work-queue",
					"prefect.resource.id": relatedWorkQueue["prefect.resource.id"],
				}
			: {},
		after: [],
		expect: [event.event],
		for_each: ["prefect.resource.id"],
		posture: "Reactive",
		threshold: 1,
		within: 0,
	};

	return {
		trigger,
		triggerTemplate: "custom",
	};
}

/**
 * Creates a basic custom trigger for events that don't have special handling.
 */
function createCustomTrigger(event: Event): EventToTriggerResult {
	return {
		trigger: {
			type: "event",
			match: {
				"prefect.resource.id": event.resource["prefect.resource.id"],
			},
			match_related: {},
			after: [],
			expect: [event.event],
			for_each: [],
			posture: "Reactive",
			threshold: 1,
			within: 0,
		},
		triggerTemplate: "custom",
	};
}

/**
 * Formats a date to YYYY-MM-DD string format for use in URL search parameters.
 *
 * @param date - The date to format (can be a Date object or ISO string)
 * @returns The formatted date string in YYYY-MM-DD format
 *
 * @example
 * formatEventDate(new Date("2024-01-15T10:30:00Z")) // returns "2024-01-15"
 * formatEventDate("2024-01-15T10:30:00Z") // returns "2024-01-15"
 */
export function formatEventDate(date: Date | string): string {
	const dateObj = typeof date === "string" ? new Date(date) : date;
	return dateObj.toISOString().split("T")[0];
}
