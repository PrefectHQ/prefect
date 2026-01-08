import { TriggerDetailsCompound } from "./trigger-details-compound";
import { TriggerDetailsCustom } from "./trigger-details-custom";
import { TriggerDetailsDeploymentStatus } from "./trigger-details-deployment-status";
import { TriggerDetailsFlowRunState } from "./trigger-details-flow-run-state";
import { TriggerDetailsSequence } from "./trigger-details-sequence";
import { TriggerDetailsWorkPoolStatus } from "./trigger-details-work-pool-status";
import { TriggerDetailsWorkQueueStatus } from "./trigger-details-work-queue-status";
import {
	type AutomationTrigger,
	type AutomationTriggerEventPosture,
	type EventTrigger,
	getAutomationTriggerTemplate,
	isCompoundTrigger,
	isEventTrigger,
	isSequenceTrigger,
	type WorkQueueStatusTriggerStatus,
} from "./trigger-utils";

type TriggerDetailsProps = {
	trigger: AutomationTrigger;
};

type DeploymentStatus = "ready" | "not_ready";
type WorkPoolStatusType = "READY" | "NOT_READY" | "PAUSED";

function asArray<T>(value: T | T[] | undefined | null): T[] {
	if (value === undefined || value === null) {
		return [];
	}
	return Array.isArray(value) ? value : [value];
}

function getMatchValue(
	trigger: EventTrigger,
	key: string,
): string | string[] | undefined {
	const match = trigger.match;
	if (match && typeof match === "object") {
		return (match as Record<string, string | string[] | undefined>)[key];
	}
	return undefined;
}

function getMatchRelatedValue(trigger: EventTrigger, key: string): string[] {
	const matchRelated = trigger.match_related;
	if (!matchRelated) {
		return [];
	}

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

function fromResourceId(resource: string, value: unknown): string[] {
	if (value === undefined || value === null) {
		return [];
	}

	const values = asArray(value as string | string[]);

	if (values.includes(`${resource}.*`)) {
		return [];
	}

	return values
		.filter((v) => v.startsWith(resource))
		.map((v) => {
			const parts = v.split(`${resource}.`);
			return parts[1] ?? "";
		})
		.filter((id) => id !== "" && id !== "*");
}

function fromStateNameEvents(events: string[]): string[] {
	if (events.includes("prefect.flow-run.*")) {
		return [];
	}

	return events
		.filter((event) => event.startsWith("prefect.flow-run."))
		.map((event) => {
			const parts = event.split("prefect.flow-run.");
			return parts[1] ?? "";
		})
		.filter((name) => name !== "");
}

function extractFlowRunStateProps(trigger: EventTrigger): {
	flowIds: string[];
	tags: string[];
	posture: AutomationTriggerEventPosture;
	states: string[];
	time?: number;
} {
	const matchRelatedResourceIds = getMatchRelatedValue(
		trigger,
		"prefect.resource.id",
	);

	const flowIds = fromResourceId("prefect.flow", matchRelatedResourceIds);
	const tags = fromResourceId("prefect.tag", matchRelatedResourceIds);

	const posture = trigger.posture;
	const states =
		posture === "Reactive"
			? fromStateNameEvents(trigger.expect ?? [])
			: fromStateNameEvents(trigger.after ?? []);

	return {
		flowIds,
		tags,
		posture,
		states,
		time: trigger.within,
	};
}

const DEPLOYMENT_STATUS_EVENT_TO_STATUS: Record<string, DeploymentStatus> = {
	"prefect.deployment.ready": "ready",
	"prefect.deployment.not-ready": "not_ready",
	"prefect.deployment.disabled": "not_ready",
};

function extractDeploymentStatusProps(trigger: EventTrigger): {
	deploymentIds: string[];
	posture: AutomationTriggerEventPosture;
	status: DeploymentStatus;
	time?: number;
} {
	const resourceIdValue = getMatchValue(trigger, "prefect.resource.id");
	const deploymentIds = fromResourceId("prefect.deployment", resourceIdValue);

	const posture = trigger.posture;
	const statusEvents = posture === "Reactive" ? trigger.expect : trigger.after;

	let status: DeploymentStatus = "ready";
	for (const event of statusEvents ?? []) {
		if (event in DEPLOYMENT_STATUS_EVENT_TO_STATUS) {
			status = DEPLOYMENT_STATUS_EVENT_TO_STATUS[event];
			break;
		}
	}

	return {
		deploymentIds,
		posture,
		status,
		time: trigger.within,
	};
}

const WORK_POOL_STATUS_EVENT_TO_STATUS: Record<string, WorkPoolStatusType> = {
	"prefect.work-pool.ready": "READY",
	"prefect.work-pool.not-ready": "NOT_READY",
	"prefect.work-pool.not_ready": "NOT_READY",
	"prefect.work-pool.paused": "PAUSED",
};

function extractWorkPoolStatusProps(trigger: EventTrigger): {
	workPoolIds: string[];
	posture: AutomationTriggerEventPosture;
	status: WorkPoolStatusType;
	time?: number;
} {
	const resourceIdValue = getMatchValue(trigger, "prefect.resource.id");
	const workPoolIds = fromResourceId("prefect.work-pool", resourceIdValue);

	const posture = trigger.posture;
	const statusEvents = posture === "Reactive" ? trigger.expect : trigger.after;

	let status: WorkPoolStatusType = "READY";
	for (const event of statusEvents ?? []) {
		if (event in WORK_POOL_STATUS_EVENT_TO_STATUS) {
			status = WORK_POOL_STATUS_EVENT_TO_STATUS[event];
			break;
		}
	}

	return {
		workPoolIds,
		posture,
		status,
		time: trigger.within,
	};
}

const WORK_QUEUE_STATUS_EVENT_TO_STATUS: Record<
	string,
	WorkQueueStatusTriggerStatus
> = {
	"prefect.work-queue.ready": "READY",
	"prefect.work-queue.not-ready": "NOT_READY",
	"prefect.work-queue.paused": "PAUSED",
};

function extractWorkQueueStatusProps(trigger: EventTrigger): {
	workQueueIds: string[];
	workPoolNames: string[];
	posture: AutomationTriggerEventPosture;
	status: WorkQueueStatusTriggerStatus;
	time?: number;
} {
	const resourceIdValue = getMatchValue(trigger, "prefect.resource.id");
	const workQueueIds = fromResourceId("prefect.work-queue", resourceIdValue);

	const matchRelatedResourceIds = getMatchRelatedValue(
		trigger,
		"prefect.resource.id",
	);
	const workPoolNames = fromResourceId(
		"prefect.work-pool",
		matchRelatedResourceIds,
	);

	const posture = trigger.posture;
	const statusEvents = posture === "Reactive" ? trigger.expect : trigger.after;

	let status: WorkQueueStatusTriggerStatus = "READY";
	for (const event of statusEvents ?? []) {
		if (event in WORK_QUEUE_STATUS_EVENT_TO_STATUS) {
			status = WORK_QUEUE_STATUS_EVENT_TO_STATUS[event];
			break;
		}
	}

	return {
		workQueueIds,
		workPoolNames,
		posture,
		status,
		time: trigger.within,
	};
}

export const TriggerDetails = ({ trigger }: TriggerDetailsProps) => {
	if (isCompoundTrigger(trigger)) {
		return <TriggerDetailsCompound trigger={trigger} />;
	}

	if (isSequenceTrigger(trigger)) {
		return <TriggerDetailsSequence trigger={trigger} />;
	}

	if (!isEventTrigger(trigger)) {
		return <TriggerDetailsCustom />;
	}

	const template = getAutomationTriggerTemplate(trigger);

	switch (template) {
		case "flow-run-state":
			return (
				<TriggerDetailsFlowRunState {...extractFlowRunStateProps(trigger)} />
			);
		case "deployment-status":
			return (
				<TriggerDetailsDeploymentStatus
					{...extractDeploymentStatusProps(trigger)}
				/>
			);
		case "work-pool-status":
			return (
				<TriggerDetailsWorkPoolStatus
					{...extractWorkPoolStatusProps(trigger)}
				/>
			);
		case "work-queue-status":
			return (
				<TriggerDetailsWorkQueueStatus
					{...extractWorkQueueStatusProps(trigger)}
				/>
			);
		default:
			return <TriggerDetailsCustom />;
	}
};
