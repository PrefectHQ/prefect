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
			// Return fields in same order as Vue for JSON tab visual parity
			return {
				type: "event",
				match: { "prefect.resource.id": "prefect.deployment.*" },
				match_related: {},
				after: [],
				expect: ["prefect.deployment.not-ready"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
		case "work-pool-status":
			// Return fields in same order as Vue for JSON tab visual parity
			return {
				type: "event",
				match: { "prefect.resource.id": "prefect.work-pool.*" },
				match_related: {},
				after: [],
				expect: [
					"prefect.work-pool.not-ready",
					// compatibility with old event name
					"prefect.work-pool.not_ready",
				],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
		case "work-queue-status":
			// Return fields in same order as Vue for JSON tab visual parity
			return {
				type: "event",
				match: { "prefect.resource.id": "prefect.work-queue.*" },
				match_related: {},
				after: [],
				expect: ["prefect.work-queue.not-ready"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
		case "custom":
			// Return fields in same order as Vue for JSON tab visual parity
			// Include sensible defaults so users see a working example
			return {
				type: "event",
				match: { "prefect.resource.id": ["prefect.flow-run.*"] },
				match_related: {},
				after: [],
				expect: ["prefect.flow-run.Failed"],
				for_each: [],
				posture: "Reactive",
				threshold: 5,
				within: 60,
			};
		default:
			return BASE_TRIGGER;
	}
};
