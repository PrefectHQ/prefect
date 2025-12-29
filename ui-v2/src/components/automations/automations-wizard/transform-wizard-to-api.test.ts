import { describe, expect, it } from "vitest";
import { transformWizardToApiPayload } from "./transform-wizard-to-api";

describe("transformWizardToApiPayload", () => {
	it("transforms wizard values to API payload", () => {
		const wizardValues = {
			name: "My Automation",
			description: "A test automation",
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
				expect: ["prefect.flow-run.Completed"],
			},
			actions: [{ type: "cancel-flow-run" as const }],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.name).toBe("My Automation");
		expect(result.description).toBe("A test automation");
		expect(result.enabled).toBe(true);
		expect(result.trigger).toEqual(wizardValues.trigger);
		expect(result.actions).toEqual(wizardValues.actions);
	});

	it("handles missing description", () => {
		const wizardValues = {
			name: "My Automation",
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
			actions: [{ type: "cancel-flow-run" as const }],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.description).toBe("");
	});

	it("handles undefined description", () => {
		const wizardValues = {
			name: "My Automation",
			description: undefined,
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
			actions: [{ type: "cancel-flow-run" as const }],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.description).toBe("");
	});

	it("always sets enabled to true", () => {
		const wizardValues = {
			name: "My Automation",
			trigger: {
				type: "event" as const,
				posture: "Proactive" as const,
				threshold: 5,
				within: 300,
			},
			actions: [{ type: "do-nothing" as const }],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.enabled).toBe(true);
	});

	it("preserves trigger configuration", () => {
		const wizardValues = {
			name: "Complex Trigger Automation",
			trigger: {
				type: "event" as const,
				posture: "Proactive" as const,
				threshold: 10,
				within: 600,
				match: { "prefect.resource.id": "my-resource" },
				for_each: ["prefect.resource.id"],
			},
			actions: [{ type: "cancel-flow-run" as const }],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.trigger).toEqual(wizardValues.trigger);
	});

	it("preserves multiple actions", () => {
		const wizardValues = {
			name: "Multi-Action Automation",
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
			actions: [
				{ type: "cancel-flow-run" as const },
				{ type: "do-nothing" as const },
			],
		};

		const result = transformWizardToApiPayload(wizardValues);

		expect(result.actions).toHaveLength(2);
		expect(result.actions).toEqual(wizardValues.actions);
	});
});
