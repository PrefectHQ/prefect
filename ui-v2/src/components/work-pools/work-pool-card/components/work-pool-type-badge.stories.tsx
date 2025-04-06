import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolTypeBadge } from "./work-pool-type-badge";

const meta: Meta<typeof WorkPoolTypeBadge> = {
	title: "Components/WorkPools/WorkPoolTypeBadge",
	component: WorkPoolTypeBadge,
	argTypes: {
		type: {
			control: "select",
			options: [
				"kubernetes",
				"process",
				"ecs",
				"azure-container-instance",
				"docker",
				"cloud-run",
				"cloud-run-v2",
				"vertex-ai",
				"kubernetes",
			],
			description: "The type of work pool to display a badge for",
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolTypeBadge>;

export const Kubernetes: Story = {
	args: {
		type: "kubernetes",
	},
};

export const Process: Story = {
	args: {
		type: "process",
	},
};

export const Docker: Story = {
	args: {
		type: "docker",
	},
};

export const VertexAI: Story = {
	args: {
		type: "vertex-ai",
	},
};

export const ECS: Story = {
	args: {
		type: "ecs",
	},
};

export const AzureContainerInstance: Story = {
	args: {
		type: "azure-container-instance",
	},
};

export const CloudRun: Story = {
	args: {
		type: "cloud-run",
	},
};

export const CloudRunV2: Story = {
	args: {
		type: "cloud-run-v2",
	},
};
