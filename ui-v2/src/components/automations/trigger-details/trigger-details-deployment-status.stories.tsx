import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerDetailsDeploymentStatus } from "./trigger-details-deployment-status";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsDeploymentStatus",
	component: TriggerDetailsDeploymentStatus,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof TriggerDetailsDeploymentStatus>;

export default meta;

type Story = StoryObj<typeof TriggerDetailsDeploymentStatus>;

export const AnyDeploymentReactiveReady: Story = {
	name: "Any Deployment - Reactive - Ready",
	args: {
		deploymentIds: [],
		posture: "Reactive",
		status: "ready",
	},
};

export const AnyDeploymentReactiveNotReady: Story = {
	name: "Any Deployment - Reactive - Not Ready",
	args: {
		deploymentIds: [],
		posture: "Reactive",
		status: "not_ready",
	},
};

export const AnyDeploymentProactiveNotReady: Story = {
	name: "Any Deployment - Proactive - Not Ready",
	args: {
		deploymentIds: [],
		posture: "Proactive",
		status: "not_ready",
		time: 30,
	},
};

export const SingleDeploymentReactiveReady: Story = {
	name: "Single Deployment - Reactive - Ready",
	args: {
		deploymentIds: ["deployment-abc-123"],
		posture: "Reactive",
		status: "ready",
	},
};

export const SingleDeploymentProactiveNotReady: Story = {
	name: "Single Deployment - Proactive - Not Ready",
	args: {
		deploymentIds: ["deployment-abc-123"],
		posture: "Proactive",
		status: "not_ready",
		time: 60,
	},
};

export const MultipleDeploymentsReactiveReady: Story = {
	name: "Multiple Deployments - Reactive - Ready",
	args: {
		deploymentIds: ["my-app", "other-app"],
		posture: "Reactive",
		status: "ready",
	},
};

export const MultipleDeploymentsProactiveNotReady: Story = {
	name: "Multiple Deployments - Proactive - Not Ready",
	args: {
		deploymentIds: ["my-app", "other-app"],
		posture: "Proactive",
		status: "not_ready",
		time: 30,
	},
};

export const ThreeDeploymentsReactiveReady: Story = {
	name: "Three Deployments - Reactive - Ready",
	args: {
		deploymentIds: ["app-one", "app-two", "app-three"],
		posture: "Reactive",
		status: "ready",
	},
};

export const ProactiveLongDuration: Story = {
	name: "Proactive - Long Duration (1 hour)",
	args: {
		deploymentIds: [],
		posture: "Proactive",
		status: "not_ready",
		time: 3600,
	},
};

function TriggerDetailsDeploymentStatusStory() {
	const scenarios = [
		{
			label: "Any deployment enters ready",
			props: {
				deploymentIds: [],
				posture: "Reactive" as const,
				status: "ready" as const,
			},
		},
		{
			label: "Any deployment stays in not ready for 30 seconds",
			props: {
				deploymentIds: [],
				posture: "Proactive" as const,
				status: "not_ready" as const,
				time: 30,
			},
		},
		{
			label: "Single deployment enters ready",
			props: {
				deploymentIds: ["my-deployment"],
				posture: "Reactive" as const,
				status: "ready" as const,
			},
		},
		{
			label: "Two deployments enter ready",
			props: {
				deploymentIds: ["my-app", "other-app"],
				posture: "Reactive" as const,
				status: "ready" as const,
			},
		},
		{
			label: "Two deployments stay in not ready for 30 seconds",
			props: {
				deploymentIds: ["my-app", "other-app"],
				posture: "Proactive" as const,
				status: "not_ready" as const,
				time: 30,
			},
		},
	];

	return (
		<ul className="flex flex-col gap-4">
			{scenarios.map((scenario) => (
				<li key={scenario.label} className="border p-4 rounded">
					<div className="text-xs text-muted-foreground mb-2">
						{scenario.label}
					</div>
					<TriggerDetailsDeploymentStatus {...scenario.props} />
				</li>
			))}
		</ul>
	);
}

export const AllScenarios: Story = {
	name: "All Scenarios",
	render: () => <TriggerDetailsDeploymentStatusStory />,
};
