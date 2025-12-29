import type { components } from "@/api/prefect";

// Type aliases for OpenAPI schema types
export type EventTrigger = components["schemas"]["EventTrigger"];
export type CompoundTrigger = components["schemas"]["CompoundTrigger-Input"];
export type SequenceTrigger = components["schemas"]["SequenceTrigger-Input"];

// Union type for all automation triggers
export type AutomationTrigger =
	| EventTrigger
	| CompoundTrigger
	| SequenceTrigger;

// Template constants - following Vue implementation (5 templates)
export const AUTOMATION_TRIGGER_TEMPLATES = [
	"deployment-status",
	"flow-run-state",
	"work-pool-status",
	"work-queue-status",
	"custom",
] as const;

export type AutomationTriggerTemplate =
	(typeof AUTOMATION_TRIGGER_TEMPLATES)[number];

// Event posture types
export type AutomationTriggerEventPosture = "Reactive" | "Proactive";

// Default threshold for event triggers (from Vue implementation)
export const DEFAULT_EVENT_TRIGGER_THRESHOLD = 1;

// Event constants for each template type
export const DEPLOYMENT_STATUS_EVENTS = [
	"prefect.deployment.ready",
	"prefect.deployment.not-ready",
	"prefect.deployment.disabled",
] as const;

export const WORK_POOL_STATUS_EVENTS = [
	"prefect.work-pool.ready",
	"prefect.work-pool.not-ready",
	"prefect.work-pool.paused",
	"prefect.work-pool.not_ready",
] as const;

export const WORK_QUEUE_STATUS_EVENTS = [
	"prefect.work-queue.ready",
	"prefect.work-queue.not-ready",
	"prefect.work-queue.paused",
] as const;

// Type guard helper - check if value is a record/object
function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Primary type guards for trigger types
export function isEventTrigger(trigger: unknown): trigger is EventTrigger {
	return (
		isRecord(trigger) &&
		trigger.type === "event" &&
		(trigger.posture === "Reactive" || trigger.posture === "Proactive")
	);
}

export function isCompoundTrigger(
	trigger: unknown,
): trigger is CompoundTrigger {
	return (
		isRecord(trigger) &&
		trigger.type === "compound" &&
		Array.isArray(trigger.triggers)
	);
}

export function isSequenceTrigger(
	trigger: unknown,
): trigger is SequenceTrigger {
	return (
		isRecord(trigger) &&
		trigger.type === "sequence" &&
		Array.isArray(trigger.triggers)
	);
}

export function isAutomationTrigger(
	trigger: unknown,
): trigger is AutomationTrigger {
	return (
		isEventTrigger(trigger) ||
		isCompoundTrigger(trigger) ||
		isSequenceTrigger(trigger)
	);
}

// Helper to convert value to array (handles undefined, single value, or array)
function asArray<T>(value: T | T[] | undefined | null): T[] {
	if (value === undefined || value === null) {
		return [];
	}
	return Array.isArray(value) ? value : [value];
}

// Get match value from trigger (handles snake_case field names from OpenAPI)
function getTriggerMatchValue(
	trigger: AutomationTrigger,
	key: string,
): string[] {
	if (isEventTrigger(trigger)) {
		const match = trigger.match;
		if (match && typeof match === "object") {
			const value = (match as Record<string, unknown>)[key];
			return value ? asArray(value as string | string[]) : [];
		}
	}
	return [];
}

// Validation helper: check if match resource satisfies predicate
export function isMatchResource(
	trigger: AutomationTrigger,
	predicate: (resourceIds: string[]) => boolean,
): boolean {
	const prefectResourceIds = getTriggerMatchValue(
		trigger,
		"prefect.resource.id",
	);

	if (prefectResourceIds.length === 0) {
		return false;
	}

	return predicate(prefectResourceIds);
}

// Validation helper: check if for_each contains the expected resource
export function isForEachResource(
	trigger: AutomationTrigger,
	resource: string,
): boolean {
	if (isEventTrigger(trigger)) {
		const forEach = trigger.for_each ?? [];
		return forEach.every((value) => value.startsWith(resource));
	}
	return false;
}

// Validation helper: check if after events satisfy predicate
export function isAfterResource(
	trigger: AutomationTrigger,
	predicate: (events: string[]) => boolean,
): boolean {
	if (isEventTrigger(trigger)) {
		return predicate(trigger.after ?? []);
	}
	return false;
}

// Validation helper: check if expect events satisfy predicate
export function isExpectResource(
	trigger: AutomationTrigger,
	predicate: (events: string[]) => boolean,
): boolean {
	if (isEventTrigger(trigger)) {
		return predicate(trigger.expect ?? []);
	}
	return false;
}

// Event type checkers
function isDeploymentStatusEvent(event: string): boolean {
	return (DEPLOYMENT_STATUS_EVENTS as readonly string[]).includes(event);
}

function isWorkPoolStatusEvent(event: string): boolean {
	return (WORK_POOL_STATUS_EVENTS as readonly string[]).includes(event);
}

function isWorkQueueStatusEvent(event: string): boolean {
	return (WORK_QUEUE_STATUS_EVENTS as readonly string[]).includes(event);
}

// Template-specific type guards

/**
 * Check if trigger is a deployment-status template
 * Validates:
 * - Is an event trigger
 * - match['prefect.resource.id'] starts with 'prefect.deployment'
 * - for_each contains 'prefect.resource.id'
 * - after events are deployment status events
 * - expect events are deployment status events
 * - threshold === 1
 */
export function isDeploymentStatusTrigger(trigger: unknown): boolean {
	return (
		isEventTrigger(trigger) &&
		isMatchResource(trigger, (prefectResourceIds) =>
			prefectResourceIds.every((value) =>
				value.startsWith("prefect.deployment"),
			),
		) &&
		isForEachResource(trigger, "prefect.resource.id") &&
		isAfterResource(trigger, (triggerAfters) =>
			triggerAfters.every((after) => isDeploymentStatusEvent(after)),
		) &&
		isExpectResource(trigger, (triggerExpects) =>
			triggerExpects.every((expect) => isDeploymentStatusEvent(expect)),
		) &&
		trigger.threshold === DEFAULT_EVENT_TRIGGER_THRESHOLD
	);
}

// Helper functions for flow-run-state template validation
function getTriggerMatchRelatedValue(
	trigger: EventTrigger,
	key: string,
): string[] {
	const matchRelated = trigger.match_related;
	if (!matchRelated) {
		return [];
	}

	// match_related can be a single object or an array of objects
	const matchRelatedArray = Array.isArray(matchRelated)
		? matchRelated
		: [matchRelated];

	const values: string[] = [];
	for (const match of matchRelatedArray) {
		if (match && typeof match === "object") {
			const value = (match as Record<string, unknown>)[key];
			if (value) {
				values.push(...asArray(value as string | string[]));
			}
		}
	}
	return values;
}

function isEmptyMatchRelated(trigger: EventTrigger): boolean {
	const matchRelated = trigger.match_related;
	if (!matchRelated) {
		return true;
	}
	if (Array.isArray(matchRelated)) {
		return matchRelated.length === 0;
	}
	return Object.keys(matchRelated).length === 0;
}

function isMatchRelatedResource(
	trigger: EventTrigger,
	resource: string,
): boolean {
	const prefectResourceIds = getTriggerMatchRelatedValue(
		trigger,
		"prefect.resource.id",
	);

	if (prefectResourceIds.length === 0) {
		return false;
	}

	return prefectResourceIds.every((value) => value.startsWith(resource));
}

function isFlowRunStateTriggerMatchRelated(trigger: EventTrigger): boolean {
	return (
		isEmptyMatchRelated(trigger) ||
		isMatchRelatedResource(trigger, "prefect.flow") ||
		isMatchRelatedResource(trigger, "prefect.tag")
	);
}

/**
 * Check if trigger is a flow-run-state template
 * Validates:
 * - Is an event trigger
 * - match['prefect.resource.id'] starts with 'prefect.flow-run'
 * - for_each contains 'prefect.resource.id'
 * - after events start with 'prefect.flow-run'
 * - expect events start with 'prefect.flow-run'
 * - matchRelated is empty OR contains flow/tag patterns
 * - threshold === 1
 */
export function isFlowRunStateTrigger(trigger: unknown): boolean {
	return (
		isEventTrigger(trigger) &&
		isMatchResource(trigger, (prefectResourceIds) =>
			prefectResourceIds.every((value) => value.startsWith("prefect.flow-run")),
		) &&
		isForEachResource(trigger, "prefect.resource.id") &&
		isAfterResource(trigger, (triggerAfters) =>
			triggerAfters.every((after) => after.startsWith("prefect.flow-run")),
		) &&
		isExpectResource(trigger, (triggerExpects) =>
			triggerExpects.every((expect) => expect.startsWith("prefect.flow-run")),
		) &&
		isFlowRunStateTriggerMatchRelated(trigger) &&
		trigger.threshold === DEFAULT_EVENT_TRIGGER_THRESHOLD
	);
}

/**
 * Check if trigger is a work-pool-status template
 * Validates:
 * - Is an event trigger
 * - match['prefect.resource.id'] starts with 'prefect.work-pool'
 * - for_each contains 'prefect.resource.id'
 * - after events are work pool status events
 * - expect events are work pool status events
 * - threshold === 1
 */
export function isWorkPoolStatusTrigger(trigger: unknown): boolean {
	return (
		isEventTrigger(trigger) &&
		isMatchResource(trigger, (prefectResourceIds) =>
			prefectResourceIds.every((value) =>
				value.startsWith("prefect.work-pool"),
			),
		) &&
		isForEachResource(trigger, "prefect.resource.id") &&
		isAfterResource(trigger, (triggerAfters) =>
			triggerAfters.every((after) => isWorkPoolStatusEvent(after)),
		) &&
		isExpectResource(trigger, (triggerExpects) =>
			triggerExpects.every((expect) => isWorkPoolStatusEvent(expect)),
		) &&
		trigger.threshold === DEFAULT_EVENT_TRIGGER_THRESHOLD
	);
}

/**
 * Check if trigger is a work-queue-status template
 * Validates:
 * - Is an event trigger
 * - match['prefect.resource.id'] starts with 'prefect.work-queue'
 * - for_each contains 'prefect.resource.id'
 * - after events are work queue status events
 * - expect events are work queue status events
 * - threshold === 1
 */
export function isWorkQueueStatusTrigger(trigger: unknown): boolean {
	return (
		isEventTrigger(trigger) &&
		isMatchResource(trigger, (prefectResourceIds) =>
			prefectResourceIds.every((value) =>
				value.startsWith("prefect.work-queue"),
			),
		) &&
		isForEachResource(trigger, "prefect.resource.id") &&
		isAfterResource(trigger, (triggerAfters) =>
			triggerAfters.every((after) => isWorkQueueStatusEvent(after)),
		) &&
		isExpectResource(trigger, (triggerExpects) =>
			triggerExpects.every((expect) => isWorkQueueStatusEvent(expect)),
		) &&
		trigger.threshold === DEFAULT_EVENT_TRIGGER_THRESHOLD
	);
}

// Template check registry (excluding 'custom' which is the default)
const automationTriggerTemplateChecks: Record<
	Exclude<AutomationTriggerTemplate, "custom">,
	(trigger: unknown) => boolean
> = {
	"deployment-status": isDeploymentStatusTrigger,
	"flow-run-state": isFlowRunStateTrigger,
	"work-pool-status": isWorkPoolStatusTrigger,
	"work-queue-status": isWorkQueueStatusTrigger,
};

/**
 * Detect the template type of an automation trigger
 * Returns 'custom' if no template matches
 */
export function getAutomationTriggerTemplate(
	trigger: AutomationTrigger,
): AutomationTriggerTemplate {
	for (const [type, guard] of Object.entries(automationTriggerTemplateChecks)) {
		if (guard(trigger)) {
			return type as AutomationTriggerTemplate;
		}
	}

	return "custom";
}

// Template labels
const automationTriggerTemplateLabels: Record<
	AutomationTriggerTemplate,
	string
> = {
	"deployment-status": "Deployment status",
	"flow-run-state": "Flow run state",
	"work-pool-status": "Work pool status",
	"work-queue-status": "Work queue status",
	custom: "Custom",
};

/**
 * Get human-readable label for a trigger template
 */
export function getAutomationTriggerTemplateLabel(
	template: AutomationTriggerTemplate,
): string {
	return automationTriggerTemplateLabels[template];
}

/**
 * Get human-readable label for event posture
 * "Reactive" -> "enters"
 * "Proactive" -> "stays in"
 */
export function getAutomationTriggerEventPostureLabel(
	posture: AutomationTriggerEventPosture,
): string {
	switch (posture) {
		case "Reactive":
			return "enters";
		case "Proactive":
			return "stays in";
	}
}

/**
 * Check if a string is a valid automation trigger template
 */
export function isAutomationTriggerTemplate(
	value: string,
): value is AutomationTriggerTemplate {
	return (AUTOMATION_TRIGGER_TEMPLATES as readonly string[]).includes(value);
}

// Work queue status types and labels
export type WorkQueueStatusTriggerStatus = "READY" | "NOT_READY" | "PAUSED";

/**
 * Get human-readable label for work queue status
 * "READY" -> "Ready"
 * "NOT_READY" -> "Not Ready"
 * "PAUSED" -> "Paused"
 */
export function getWorkQueueStatusLabel(
	status: WorkQueueStatusTriggerStatus,
): string {
	switch (status) {
		case "READY":
			return "Ready";
		case "NOT_READY":
			return "Not Ready";
		case "PAUSED":
			return "Paused";
		default: {
			const exhaustive: never = status;
			throw new Error(
				`getWorkQueueStatusLabel missing case for ${exhaustive as string}`,
			);
		}
	}
}
