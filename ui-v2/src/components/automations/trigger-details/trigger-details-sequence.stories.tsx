import type { Meta, StoryObj } from "@storybook/react";
import { TriggerDetailsSequence } from "./trigger-details-sequence";
import type { SequenceTrigger } from "./trigger-utils";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsSequence",
	component: TriggerDetailsSequence,
} satisfies Meta<typeof TriggerDetailsSequence>;

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

const sequenceTriggerSingle: SequenceTrigger = {
	type: "sequence",
	triggers: [baseEventTrigger],
	within: 60,
};

const sequenceTriggerTwo: SequenceTrigger = {
	type: "sequence",
	triggers: [baseEventTrigger, baseEventTrigger],
	within: 60,
};

const sequenceTriggerThree: SequenceTrigger = {
	type: "sequence",
	triggers: [baseEventTrigger, baseEventTrigger, baseEventTrigger],
	within: 120,
};

const sequenceTriggerEmpty: SequenceTrigger = {
	type: "sequence",
	triggers: [],
	within: 60,
};

export const SingleTrigger: Story = {
	name: "Single Nested Trigger",
	args: {
		trigger: sequenceTriggerSingle,
	},
};

export const TwoTriggers: Story = {
	name: "Two Nested Triggers",
	args: {
		trigger: sequenceTriggerTwo,
	},
};

export const ThreeTriggers: Story = {
	name: "Three Nested Triggers",
	args: {
		trigger: sequenceTriggerThree,
	},
};

export const EmptyTriggers: Story = {
	name: "Empty Triggers Array",
	args: {
		trigger: sequenceTriggerEmpty,
	},
};
