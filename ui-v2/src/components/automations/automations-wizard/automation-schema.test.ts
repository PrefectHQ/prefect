import { describe, expect, it } from "vitest";
import {
	AutomationWizardSchema,
	CompoundTriggerSchema,
	EventTriggerSchema,
	SequenceTriggerSchema,
	TriggerSchema,
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

		it("validates a proactive trigger", () => {
			const trigger = {
				type: "event",
				posture: "Proactive",
				threshold: 1,
				within: 60,
			};
			expect(() => EventTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates match with array values", () => {
			const trigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
				match: {
					"prefect.resource.id": ["prefect.flow-run.1", "prefect.flow-run.2"],
				},
			};
			expect(() => EventTriggerSchema.parse(trigger)).not.toThrow();
		});
	});

	describe("CompoundTriggerSchema", () => {
		it("validates a compound trigger with require='all'", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: "all",
				within: 0,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates a compound trigger with require='any'", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: "any",
				within: 0,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates a compound trigger with numeric require", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: 2,
				within: 0,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("rejects numeric require less than 1", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: 0,
				within: 0,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).toThrow();
		});

		it("applies default values for require and within", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
			};
			const parsed = CompoundTriggerSchema.parse(trigger);
			expect(parsed.require).toBe("all");
			expect(parsed.within).toBe(0);
		});

		it("validates nested compound triggers", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "compound",
						triggers: [
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
							},
						],
						require: "all",
						within: 0,
					},
				],
				require: "all",
				within: 0,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates compound trigger with within time window", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: "all",
				within: 300,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("rejects negative within value", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: "all",
				within: -1,
			};
			expect(() => CompoundTriggerSchema.parse(trigger)).toThrow();
		});
	});

	describe("SequenceTriggerSchema", () => {
		it("validates a sequence trigger", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				within: 0,
			};
			expect(() => SequenceTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("applies default value for within", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
			};
			const parsed = SequenceTriggerSchema.parse(trigger);
			expect(parsed.within).toBe(0);
		});

		it("validates sequence trigger with within time window", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				within: 600,
			};
			expect(() => SequenceTriggerSchema.parse(trigger)).not.toThrow();
		});

		it("rejects negative within value", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				within: -1,
			};
			expect(() => SequenceTriggerSchema.parse(trigger)).toThrow();
		});

		it("validates nested sequence triggers", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "sequence",
						triggers: [
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
							},
						],
						within: 0,
					},
				],
				within: 0,
			};
			expect(() => SequenceTriggerSchema.parse(trigger)).not.toThrow();
		});
	});

	describe("TriggerSchema (discriminated union)", () => {
		it("validates event trigger", () => {
			const trigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
			const parsed = TriggerSchema.parse(trigger);
			expect(parsed.type).toBe("event");
		});

		it("validates compound trigger", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				require: "all",
				within: 0,
			};
			const parsed = TriggerSchema.parse(trigger);
			expect(parsed.type).toBe("compound");
		});

		it("validates sequence trigger", () => {
			const trigger = {
				type: "sequence",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
				],
				within: 0,
			};
			const parsed = TriggerSchema.parse(trigger);
			expect(parsed.type).toBe("sequence");
		});

		it("rejects invalid trigger type", () => {
			const trigger = {
				type: "invalid",
				triggers: [],
			};
			expect(() => TriggerSchema.parse(trigger)).toThrow();
		});

		it("validates deeply nested recursive triggers", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "sequence",
						triggers: [
							{
								type: "compound",
								triggers: [
									{
										type: "event",
										posture: "Reactive",
										threshold: 1,
										within: 0,
									},
								],
								require: "any",
								within: 0,
							},
						],
						within: 0,
					},
				],
				require: "all",
				within: 0,
			};
			expect(() => TriggerSchema.parse(trigger)).not.toThrow();
		});

		it("validates mixed trigger types in compound", () => {
			const trigger = {
				type: "compound",
				triggers: [
					{
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
					},
					{
						type: "sequence",
						triggers: [
							{
								type: "event",
								posture: "Proactive",
								threshold: 2,
								within: 60,
							},
						],
						within: 120,
					},
				],
				require: 1,
				within: 300,
			};
			expect(() => TriggerSchema.parse(trigger)).not.toThrow();
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

		it("validates a complete automation with event trigger", () => {
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

		it("validates a complete automation with compound trigger", () => {
			const automation = {
				name: "Test Automation",
				trigger: {
					type: "compound",
					triggers: [
						{
							type: "event",
							posture: "Reactive",
							threshold: 1,
							within: 0,
						},
					],
					require: "all",
					within: 0,
				},
				actions: [],
			};
			expect(() => AutomationWizardSchema.parse(automation)).not.toThrow();
		});

		it("validates a complete automation with sequence trigger", () => {
			const automation = {
				name: "Test Automation",
				trigger: {
					type: "sequence",
					triggers: [
						{
							type: "event",
							posture: "Reactive",
							threshold: 1,
							within: 0,
						},
					],
					within: 0,
				},
				actions: [],
			};
			expect(() => AutomationWizardSchema.parse(automation)).not.toThrow();
		});

		it("validates automation with nested triggers", () => {
			const automation = {
				name: "Complex Automation",
				description: "An automation with nested triggers",
				trigger: {
					type: "compound",
					triggers: [
						{
							type: "event",
							posture: "Reactive",
							threshold: 1,
							within: 0,
							match: { "prefect.resource.id": "prefect.flow-run.*" },
						},
						{
							type: "sequence",
							triggers: [
								{
									type: "event",
									posture: "Reactive",
									threshold: 1,
									within: 0,
								},
								{
									type: "event",
									posture: "Proactive",
									threshold: 1,
									within: 60,
								},
							],
							within: 120,
						},
					],
					require: "any",
					within: 300,
				},
				actions: [],
			};
			expect(() => AutomationWizardSchema.parse(automation)).not.toThrow();
		});
	});
});
