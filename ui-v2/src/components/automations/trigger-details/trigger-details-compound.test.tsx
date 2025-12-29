import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TriggerDetailsCompound } from "./trigger-details-compound";
import type { CompoundTrigger } from "./trigger-utils";

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

describe("TriggerDetailsCompound", () => {
	it("renders 'all' for require: 'all'", () => {
		const trigger: CompoundTrigger = {
			type: "compound",
			require: "all",
			triggers: [baseEventTrigger, baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring all of 2 nested triggers/i),
		).toBeInTheDocument();
	});

	it("renders 'any' for require: 'any'", () => {
		const trigger: CompoundTrigger = {
			type: "compound",
			require: "any",
			triggers: [baseEventTrigger, baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring any of 2 nested triggers/i),
		).toBeInTheDocument();
	});

	it("renders 'at least N' for numeric require", () => {
		const trigger: CompoundTrigger = {
			type: "compound",
			require: 2,
			triggers: [baseEventTrigger, baseEventTrigger, baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(
				/compound trigger requiring at least 2 of 3 nested triggers/i,
			),
		).toBeInTheDocument();
	});

	it("renders singular form for 1 nested trigger", () => {
		const trigger: CompoundTrigger = {
			type: "compound",
			require: "all",
			triggers: [baseEventTrigger],
			within: 60,
		};

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring all of 1 nested trigger\b/i),
		).toBeInTheDocument();
	});

	it("renders plural form for 0 nested triggers", () => {
		const trigger: CompoundTrigger = {
			type: "compound",
			require: "all",
			triggers: [],
			within: 60,
		};

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring all of 0 nested triggers/i),
		).toBeInTheDocument();
	});

	it("falls back to 'all' for invalid require value", () => {
		const trigger = {
			type: "compound",
			require: undefined as unknown as CompoundTrigger["require"],
			triggers: [baseEventTrigger, baseEventTrigger],
			within: 60,
		} as CompoundTrigger;

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring all of 2 nested triggers/i),
		).toBeInTheDocument();
	});

	it("handles undefined triggers gracefully", () => {
		const trigger = {
			type: "compound",
			require: "all",
			within: 60,
		} as unknown as CompoundTrigger;

		render(<TriggerDetailsCompound trigger={trigger} />);

		expect(
			screen.getByText(/compound trigger requiring all of 0 nested triggers/i),
		).toBeInTheDocument();
	});
});
