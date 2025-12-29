import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerDetails } from "./trigger-details";
import type { AutomationTrigger } from "./trigger-utils";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetails",
	component: TriggerDetails,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof TriggerDetails>;

export default meta;

type Story = StoryObj<typeof TriggerDetails>;

const flowRunStateTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const flowRunStateTriggerProactive: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {},
	after: ["prefect.flow-run.Running"],
	expect: [],
	for_each: ["prefect.resource.id"],
	posture: "Proactive",
	threshold: 1,
	within: 60,
};

const flowRunStateTriggerWithFlow: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {
		"prefect.resource.role": "flow",
		"prefect.resource.id": "prefect.flow.my-flow-id",
	},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const flowRunStateTriggerWithTags: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {
		"prefect.resource.role": "tag",
		"prefect.resource.id": ["prefect.tag.production", "prefect.tag.critical"],
	},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const deploymentStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-2",
	match: {
		"prefect.resource.id": "prefect.deployment.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.deployment.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const deploymentStatusTriggerProactive: AutomationTrigger = {
	type: "event",
	id: "trigger-2",
	match: {
		"prefect.resource.id": "prefect.deployment.*",
	},
	match_related: {},
	after: ["prefect.deployment.not-ready"],
	expect: ["prefect.deployment.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Proactive",
	threshold: 1,
	within: 30,
};

const workPoolStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-3",
	match: {
		"prefect.resource.id": "prefect.work-pool.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.work-pool.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const workPoolStatusTriggerProactive: AutomationTrigger = {
	type: "event",
	id: "trigger-3",
	match: {
		"prefect.resource.id": "prefect.work-pool.*",
	},
	match_related: {},
	after: ["prefect.work-pool.not-ready"],
	expect: ["prefect.work-pool.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Proactive",
	threshold: 1,
	within: 60,
};

const workQueueStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-4",
	match: {
		"prefect.resource.id": "prefect.work-queue.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.work-queue.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const workQueueStatusTriggerProactive: AutomationTrigger = {
	type: "event",
	id: "trigger-4",
	match: {
		"prefect.resource.id": "prefect.work-queue.*",
	},
	match_related: {},
	after: ["prefect.work-queue.not-ready"],
	expect: ["prefect.work-queue.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Proactive",
	threshold: 1,
	within: 30,
};

const compoundTriggerAll: AutomationTrigger = {
	type: "compound",
	require: "all",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const compoundTriggerAny: AutomationTrigger = {
	type: "compound",
	require: "any",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const compoundTriggerNumber: AutomationTrigger = {
	type: "compound",
	require: 2,
	triggers: [
		flowRunStateTriggerReactive,
		deploymentStatusTriggerReactive,
		workPoolStatusTriggerReactive,
	],
	within: 60,
};

const sequenceTrigger: AutomationTrigger = {
	type: "sequence",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const sequenceTriggerThree: AutomationTrigger = {
	type: "sequence",
	triggers: [
		flowRunStateTriggerReactive,
		deploymentStatusTriggerReactive,
		workPoolStatusTriggerReactive,
	],
	within: 60,
};

const customTrigger: AutomationTrigger = {
	type: "event",
	id: "trigger-custom",
	match: {
		"prefect.resource.id": "custom.resource.*",
	},
	match_related: {},
	after: ["custom.event.started"],
	expect: ["custom.event.completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 5,
	within: 300,
};

export const FlowRunStateReactive: Story = {
	name: "Flow Run State - Reactive",
	args: {
		trigger: flowRunStateTriggerReactive,
	},
};

export const FlowRunStateProactive: Story = {
	name: "Flow Run State - Proactive",
	args: {
		trigger: flowRunStateTriggerProactive,
	},
};

export const FlowRunStateWithFlow: Story = {
	name: "Flow Run State - With Specific Flow",
	args: {
		trigger: flowRunStateTriggerWithFlow,
	},
};

export const FlowRunStateWithTags: Story = {
	name: "Flow Run State - With Tags",
	args: {
		trigger: flowRunStateTriggerWithTags,
	},
};

export const DeploymentStatusReactive: Story = {
	name: "Deployment Status - Reactive",
	args: {
		trigger: deploymentStatusTriggerReactive,
	},
};

export const DeploymentStatusProactive: Story = {
	name: "Deployment Status - Proactive",
	args: {
		trigger: deploymentStatusTriggerProactive,
	},
};

export const WorkPoolStatusReactive: Story = {
	name: "Work Pool Status - Reactive",
	args: {
		trigger: workPoolStatusTriggerReactive,
	},
};

export const WorkPoolStatusProactive: Story = {
	name: "Work Pool Status - Proactive",
	args: {
		trigger: workPoolStatusTriggerProactive,
	},
};

export const WorkQueueStatusReactive: Story = {
	name: "Work Queue Status - Reactive",
	args: {
		trigger: workQueueStatusTriggerReactive,
	},
};

export const WorkQueueStatusProactive: Story = {
	name: "Work Queue Status - Proactive",
	args: {
		trigger: workQueueStatusTriggerProactive,
	},
};

export const CompoundTriggerAll: Story = {
	name: "Compound Trigger - Require All",
	args: {
		trigger: compoundTriggerAll,
	},
};

export const CompoundTriggerAny: Story = {
	name: "Compound Trigger - Require Any",
	args: {
		trigger: compoundTriggerAny,
	},
};

export const CompoundTriggerNumber: Story = {
	name: "Compound Trigger - Require 2",
	args: {
		trigger: compoundTriggerNumber,
	},
};

export const SequenceTrigger: Story = {
	name: "Sequence Trigger",
	args: {
		trigger: sequenceTrigger,
	},
};

export const SequenceTriggerThree: Story = {
	name: "Sequence Trigger - Three Steps",
	args: {
		trigger: sequenceTriggerThree,
	},
};

export const CustomTrigger: Story = {
	name: "Custom Trigger",
	args: {
		trigger: customTrigger,
	},
};

function TriggerDetailsAllScenarios() {
	const scenarios: Array<{ label: string; trigger: AutomationTrigger }> = [
		{
			label: "Flow Run State - Reactive - Completed",
			trigger: flowRunStateTriggerReactive,
		},
		{
			label: "Flow Run State - Proactive - Running for 60s",
			trigger: flowRunStateTriggerProactive,
		},
		{
			label: "Deployment Status - Reactive - Ready",
			trigger: deploymentStatusTriggerReactive,
		},
		{
			label: "Deployment Status - Proactive - Not Ready for 30s",
			trigger: deploymentStatusTriggerProactive,
		},
		{
			label: "Work Pool Status - Reactive - Ready",
			trigger: workPoolStatusTriggerReactive,
		},
		{
			label: "Work Queue Status - Reactive - Ready",
			trigger: workQueueStatusTriggerReactive,
		},
		{
			label: "Compound Trigger - All of 2",
			trigger: compoundTriggerAll,
		},
		{
			label: "Compound Trigger - Any of 3",
			trigger: compoundTriggerNumber,
		},
		{
			label: "Sequence Trigger - 2 steps",
			trigger: sequenceTrigger,
		},
		{
			label: "Custom Trigger",
			trigger: customTrigger,
		},
	];

	return (
		<ul className="flex flex-col gap-4">
			{scenarios.map((scenario) => (
				<li key={scenario.label} className="border p-4 rounded">
					<div className="text-xs text-muted-foreground mb-2">
						{scenario.label}
					</div>
					<TriggerDetails trigger={scenario.trigger} />
				</li>
			))}
		</ul>
	);
}

export const AllScenarios: Story = {
	name: "All Scenarios",
	render: () => <TriggerDetailsAllScenarios />,
};
