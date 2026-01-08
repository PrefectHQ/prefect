import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerDetailsFlowRunState } from "./trigger-details-flow-run-state";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsFlowRunState",
	component: TriggerDetailsFlowRunState,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof TriggerDetailsFlowRunState>;

export default meta;

type Story = StoryObj<typeof meta>;

export const AnyFlowRunEnteringState: Story = {
	name: "Any flow run entering a state",
	args: {
		flowIds: [],
		tags: [],
		posture: "Reactive",
		states: ["COMPLETED"],
	},
};

export const SpecificFlowEnteringState: Story = {
	name: "Specific flow entering a state",
	args: {
		flowIds: ["00000000-0000-0000-0000-000000000001"],
		tags: [],
		posture: "Reactive",
		states: ["COMPLETED"],
	},
};

export const MultipleFlowsEnteringState: Story = {
	name: "Multiple flows entering a state",
	args: {
		flowIds: [
			"00000000-0000-0000-0000-000000000001",
			"00000000-0000-0000-0000-000000000002",
		],
		tags: [],
		posture: "Reactive",
		states: ["COMPLETED"],
	},
};

export const WithTags: Story = {
	name: "With tags",
	args: {
		flowIds: [],
		tags: ["production", "critical"],
		posture: "Reactive",
		states: ["FAILED"],
	},
};

export const ProactiveWithTime: Story = {
	name: "Proactive posture with time",
	args: {
		flowIds: [],
		tags: [],
		posture: "Proactive",
		states: ["RUNNING"],
		time: 30,
	},
};

export const ProactiveWithLongerTime: Story = {
	name: "Proactive posture with longer time",
	args: {
		flowIds: [],
		tags: [],
		posture: "Proactive",
		states: ["PENDING"],
		time: 3600,
	},
};

export const MultipleStates: Story = {
	name: "Multiple states",
	args: {
		flowIds: [],
		tags: [],
		posture: "Reactive",
		states: ["COMPLETED", "FAILED", "CRASHED"],
	},
};

export const AnyState: Story = {
	name: "Any state (empty states array)",
	args: {
		flowIds: [],
		tags: [],
		posture: "Reactive",
		states: [],
	},
};

export const ComplexTrigger: Story = {
	name: "Complex trigger with all options",
	args: {
		flowIds: ["00000000-0000-0000-0000-000000000001"],
		tags: ["production"],
		posture: "Proactive",
		states: ["FAILED", "CRASHED"],
		time: 60,
	},
};
