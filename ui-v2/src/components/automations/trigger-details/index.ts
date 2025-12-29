export { TriggerDetails } from "./trigger-details";
export { TriggerDetailsCompound } from "./trigger-details-compound";
export { TriggerDetailsCustom } from "./trigger-details-custom";
export { TriggerDetailsDeploymentStatus } from "./trigger-details-deployment-status";
export { TriggerDetailsFlowRunState } from "./trigger-details-flow-run-state";
export { TriggerDetailsSequence } from "./trigger-details-sequence";
export { TriggerDetailsWorkPoolStatus } from "./trigger-details-work-pool-status";
export { TriggerDetailsWorkQueueStatus } from "./trigger-details-work-queue-status";
export {
	// Constants
	AUTOMATION_TRIGGER_TEMPLATES,
	type AutomationTrigger,
	type AutomationTriggerEventPosture,
	type AutomationTriggerTemplate,
	type CompoundTrigger,
	DEFAULT_EVENT_TRIGGER_THRESHOLD,
	DEPLOYMENT_STATUS_EVENTS,
	// Types
	type EventTrigger,
	getAutomationTriggerEventPostureLabel,
	getAutomationTriggerTemplate,
	// Label functions
	getAutomationTriggerTemplateLabel,
	// Work queue status utilities
	getWorkQueueStatusLabel,
	isAfterResource,
	isAutomationTrigger,
	isAutomationTriggerTemplate,
	isCompoundTrigger,
	// Template detection
	isDeploymentStatusTrigger,
	// Type guards
	isEventTrigger,
	isExpectResource,
	isFlowRunStateTrigger,
	isForEachResource,
	// Validation helpers
	isMatchResource,
	isSequenceTrigger,
	isWorkPoolStatusTrigger,
	isWorkQueueStatusTrigger,
	type SequenceTrigger,
	WORK_POOL_STATUS_EVENTS,
	WORK_QUEUE_STATUS_EVENTS,
	type WorkQueueStatusTriggerStatus,
} from "./trigger-utils";
