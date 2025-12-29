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
} from "./trigger-utils";
