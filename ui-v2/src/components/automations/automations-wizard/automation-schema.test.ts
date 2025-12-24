import { describe, expect, it } from "vitest";
import {
	AutomationWizardSchema,
	EventTriggerSchema,
	TriggerTemplateSchema,
} from "./automation-schema";

describe("Trigger Schemas", () => {
	describe("TriggerTemplateSchema", () => {
		it("accepts valid template values", () => {
			expect(TriggerTemplateSchema.parse("flow-run-state")).toBe(
				"flow-run-state",
			);
			expect(TriggerTemplateSchema.parse("deployment-status")).toBe(
				"deployment-status",
			);
		});

		it("rejects invalid template values", () => {
			expect(() => TriggerTemplateSchema.parse("invalid")).toThrow();
		});
	});

	describe("EventTriggerSchema", () => {
		it("validates a minimal reactive trigger", () => {
			const trigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
			expect(() => EventTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates a trigger with match conditions", () => {
			const trigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
				match: { "prefect.resource.id": "prefect.flow-run.*" },
				expect: ["prefect.flow-run.Completed"],
			};
			expect(() => EventTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("rejects threshold less than 1", () => {
			const trigger = {
				type: "event",
				posture: "Reactive",
				threshold: 0,
				within: 0,
			};
			expect(() => EventTriggerSchema.parse(trigger)).toThrow();
		});
	});

	describe("AutomationWizardSchema", () => {
		it("requires a trigger field", () => {
			const automation = {
				name: "Test Automation",
				actions: [],
			};
			expect(() => AutomationWizardSchema.parse(automation)).toThrow();
		});

		it("validates a complete automation with trigger", () => {
			const automation = {
				name: "Test Automation",
				trigger: {
					type: "event",
					posture: "Reactive",
					threshold: 1,
					within: 0,
				},
				actions: [],
			};
			expect(() => AutomationWizardSchema.parse(automation)).not.toThrow();
		});
	});
});
