import type { Meta, StoryObj } from "@storybook/react";

import { DeploymentStatusBadge } from "./deployment-status-badge";

const meta: Meta<typeof DeploymentStatusBadge> = {
	title: "Components/Deployments/DeploymentStatusBadge",
	component: DeploymentStatusBadge,
	parameters: {
		layout: "centered",
	},
};

export default meta;
type Story = StoryObj<typeof DeploymentStatusBadge>;

export const Ready: Story = {
	args: {
		deployment: {
			status: "READY",
			paused: false,
		},
	},
};

export const NotReady: Story = {
	args: {
		deployment: {
			status: "NOT_READY",
			paused: false,
		},
	},
};

export const Paused: Story = {
	args: {
		deployment: {
			status: "READY",
			paused: true,
		},
	},
};

export const AllStatuses: Story = {
	render: () => (
		<div className="flex flex-col space-y-2">
			<div className="flex items-center space-x-2">
				<DeploymentStatusBadge
					deployment={{ status: "READY", paused: false }}
				/>
				<span className="text-sm text-muted-foreground">
					Deployment is ready and accepting work
				</span>
			</div>
			<div className="flex items-center space-x-2">
				<DeploymentStatusBadge
					deployment={{ status: "NOT_READY", paused: false }}
				/>
				<span className="text-sm text-muted-foreground">
					Deployment is not ready
				</span>
			</div>
			<div className="flex items-center space-x-2">
				<DeploymentStatusBadge deployment={{ status: "READY", paused: true }} />
				<span className="text-sm text-muted-foreground">
					Deployment is paused
				</span>
			</div>
		</div>
	),
};

export const InContext: Story = {
	render: () => (
		<div className="max-w-md p-4 border rounded-lg">
			<div className="flex items-center justify-between mb-2">
				<h3 className="font-semibold">My Deployment</h3>
				<DeploymentStatusBadge
					deployment={{ status: "READY", paused: false }}
				/>
			</div>
			<p className="text-sm text-muted-foreground">
				A sample deployment demonstrating the status badge in context.
			</p>
		</div>
	),
};
