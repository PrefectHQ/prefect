import type { EventTrigger } from "@/components/automations/automations-wizard/automation-schema";
import type { TriggerTemplate } from "@/components/automations/automations-wizard/automations-trigger-template-select";

const BASE_TRIGGER: EventTrigger = {
	type: "event",
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

export const getDefaultTriggerForTemplate = (
	template: TriggerTemplate,
): EventTrigger => {
	switch (template) {
		case "flow-run-state":
			return {
				...BASE_TRIGGER,
				match: { "prefect.resource.id": "prefect.flow-run.*" },
				for_each: ["prefect.resource.id"],
			};
		case "deployment-status":
			return {
				...BASE_TRIGGER,
				match: { "prefect.resource.id": "prefect.deployment.*" },
				for_each: ["prefect.resource.id"],
			};
		case "work-pool-status":
			return {
				...BASE_TRIGGER,
				match: { "prefect.resource.id": "prefect.work-pool.*" },
				for_each: ["prefect.resource.id"],
			};
		case "work-queue-status":
			return {
				...BASE_TRIGGER,
				match: { "prefect.resource.id": "prefect.work-queue.*" },
				for_each: ["prefect.resource.id"],
			};
		case "custom":
			return BASE_TRIGGER;
		default:
			return BASE_TRIGGER;
	}
};
