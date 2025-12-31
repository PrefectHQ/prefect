import type { EventTrigger } from "@/components/automations/automations-wizard/automation-schema";
import type { TriggerTemplate } from "@/components/automations/automations-wizard/automations-trigger-template-select";

const BASE_TRIGGER: EventTrigger = {
	type: "event",
	match: {},
	match_related: {},
	after: [],
	expect: [],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

export const getDefaultTriggerForTemplate = (
	template: TriggerTemplate,
): EventTrigger => {
	switch (template) {
		case "flow-run-state":
			// Return fields in same order as Vue for JSON tab visual parity
			return {
				type: "event",
				match: { "prefect.resource.id": "prefect.flow-run.*" },
				match_related: {},
				after: [],
				expect: ["prefect.flow-run.*"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
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
