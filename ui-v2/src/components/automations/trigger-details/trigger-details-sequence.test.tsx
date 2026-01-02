import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TriggerDetailsSequence } from "./trigger-details-sequence";
import type { SequenceTrigger } from "./trigger-utils";

const baseEventTrigger = {
	type: "event" as const,
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive" as const,
	threshold: 1,
	within: 0,
};

describe("TriggerDetailsSequence", () => {
	it("renders singular form for 1 nested trigger", () => {
		const trigger: SequenceTrigger = {
			type: "sequence",
			triggers: [baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsSequence trigger={trigger} />);

		expect(
			screen.getByText(/sequence trigger with 1 nested trigger/i),
		).toBeInTheDocument();
		expect(screen.getByText(/must fire in order/i)).toBeInTheDocument();
	});

	it("renders plural form for 2 nested triggers", () => {
		const trigger: SequenceTrigger = {
			type: "sequence",
			triggers: [baseEventTrigger, baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsSequence trigger={trigger} />);

		expect(
			screen.getByText(/sequence trigger with 2 nested triggers/i),
		).toBeInTheDocument();
		expect(screen.getByText(/must fire in order/i)).toBeInTheDocument();
	});

	it("renders plural form for 3 nested triggers", () => {
		const trigger: SequenceTrigger = {
			type: "sequence",
			triggers: [baseEventTrigger, baseEventTrigger, baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsSequence trigger={trigger} />);

		expect(
			screen.getByText(/sequence trigger with 3 nested triggers/i),
		).toBeInTheDocument();
	});

	it("renders 0 nested triggers for empty triggers array", () => {
		const trigger: SequenceTrigger = {
			type: "sequence",
			triggers: [],
			within: 60,
		};

		render(<TriggerDetailsSequence trigger={trigger} />);

		expect(
			screen.getByText(/sequence trigger with 0 nested triggers/i),
		).toBeInTheDocument();
		expect(screen.getByText(/must fire in order/i)).toBeInTheDocument();
	});

	it("handles undefined triggers gracefully", () => {
		const trigger = {
			type: "sequence",
			within: 60,
		} as unknown as SequenceTrigger;

		render(<TriggerDetailsSequence trigger={trigger} />);

		expect(
			screen.getByText(/sequence trigger with 0 nested triggers/i),
		).toBeInTheDocument();
	});
});
