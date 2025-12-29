import type { Meta, StoryObj } from "@storybook/react";
import { TriggerDetailsCompound } from "./trigger-details-compound";
import type { CompoundTrigger } from "./trigger-utils";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsCompound",
	component: TriggerDetailsCompound,
} satisfies Meta<typeof TriggerDetailsCompound>;

export default meta;

type Story = StoryObj<typeof meta>;

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

const compoundTriggerAllTwo: CompoundTrigger = {
	type: "compound",
	require: "all",
	triggers: [baseEventTrigger, baseEventTrigger],
	within: 60,
};

const compoundTriggerAnyTwo: CompoundTrigger = {
	type: "compound",
	require: "any",
	triggers: [baseEventTrigger, baseEventTrigger],
	within: 60,
};

const compoundTriggerNumericThree: CompoundTrigger = {
	type: "compound",
	require: 2,
	triggers: [baseEventTrigger, baseEventTrigger, baseEventTrigger],
	within: 60,
};

const compoundTriggerSingle: CompoundTrigger = {
	type: "compound",
	require: "all",
	triggers: [baseEventTrigger],
	within: 60,
};

const compoundTriggerEmpty: CompoundTrigger = {
	type: "compound",
	require: "all",
	triggers: [],
	within: 60,
};

export const RequireAll: Story = {
	name: "Require All - Two Triggers",
	args: {
		trigger: compoundTriggerAllTwo,
	},
};

export const RequireAny: Story = {
	name: "Require Any - Two Triggers",
	args: {
		trigger: compoundTriggerAnyTwo,
	},
};

export const RequireNumeric: Story = {
	name: "Require At Least 2 - Three Triggers",
	args: {
		trigger: compoundTriggerNumericThree,
	},
};

export const SingleTrigger: Story = {
	name: "Single Nested Trigger",
	args: {
		trigger: compoundTriggerSingle,
	},
};

export const EmptyTriggers: Story = {
	name: "Empty Triggers Array",
	args: {
		trigger: compoundTriggerEmpty,
	},
};
