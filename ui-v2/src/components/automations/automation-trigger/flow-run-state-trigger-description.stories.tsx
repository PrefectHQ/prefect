import type { Meta, StoryObj } from "@storybook/react";
import type { AutomationTrigger } from "@/components/automations/trigger-details";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunStateTriggerDescription } from "./flow-run-state-trigger-description";

const meta = {
	title:
		"Components/Automations/AutomationTrigger/FlowRunStateTriggerDescription",
	component: FlowRunStateTriggerDescription,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof FlowRunStateTriggerDescription>;

export default meta;

type Story = StoryObj<typeof meta>;

type ResourceSpecification = { [key: string]: string | string[] };

function createFlowRunStateTrigger(
	overrides: Partial<{
		posture: "Reactive" | "Proactive";
		expect: string[];
		after: string[];
		within: number;
		match_related: ResourceSpecification[];
	}> = {},
): AutomationTrigger {
	const posture = overrides.posture ?? "Reactive";
	return {
		type: "event",
		posture,
		match: {
			"prefect.resource.id": "prefect.flow-run.*",
		},
		match_related: overrides.match_related ?? [],
		for_each: ["prefect.resource.id"],
		expect: posture === "Reactive" ? (overrides.expect ?? []) : [],
		after: posture === "Proactive" ? (overrides.after ?? []) : [],
		threshold: 1,
		within: overrides.within ?? 0,
	};
}

export const AnyFlowRunEnteringState: Story = {
	name: "Any flow run entering a state",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
		}),
	},
};

export const SpecificFlowEnteringState: Story = {
	name: "Specific flow entering a state",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.00000000-0000-0000-0000-000000000001",
					],
				},
			],
		}),
	},
};

export const MultipleFlowsEnteringState: Story = {
	name: "Multiple flows entering a state",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.00000000-0000-0000-0000-000000000001",
						"prefect.flow.00000000-0000-0000-0000-000000000002",
					],
				},
			],
		}),
	},
};

export const WithTags: Story = {
	name: "With tags",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Failed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.tag.production",
						"prefect.tag.critical",
					],
				},
			],
		}),
	},
};

export const ProactiveWithTime: Story = {
	name: "Proactive posture with time",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Running"],
			within: 30,
		}),
	},
};

export const ProactiveWithLongerTime: Story = {
	name: "Proactive posture with longer time",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Pending"],
			within: 3600,
		}),
	},
};

export const MultipleStates: Story = {
	name: "Multiple states",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: [
				"prefect.flow-run.Completed",
				"prefect.flow-run.Failed",
				"prefect.flow-run.Crashed",
			],
		}),
	},
};

export const AnyState: Story = {
	name: "Any state (empty states array)",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Reactive",
			expect: [],
		}),
	},
};

export const ComplexTrigger: Story = {
	name: "Complex trigger with all options",
	args: {
		trigger: createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Failed", "prefect.flow-run.Crashed"],
			within: 60,
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.00000000-0000-0000-0000-000000000001",
						"prefect.tag.production",
					],
				},
			],
		}),
	},
};
