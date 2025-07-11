import type { Meta, StoryObj } from "@storybook/react";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolCard } from "./work-pool-card";

const meta: Meta<typeof WorkPoolCard> = {
	title: "Components/WorkPools/Card",
	component: WorkPoolCard,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {},
};

export default meta;
type Story = StoryObj<typeof WorkPoolCard>;

export const Default: Story = {
	args: {
		workPool: createFakeWorkPool(),
	},
};

export const UnlimitedConcurrency: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			concurrency_limit: null,
		},
	},
};

export const Kubernetes: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "kubernetes",
		},
	},
};

export const Process: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "process",
		},
	},
};

export const Docker: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "docker",
		},
	},
};

export const VertexAI: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "vertex-ai",
		},
	},
};

export const ECS: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "ecs",
		},
	},
};

export const AzureContainerInstance: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "azure-container-instance",
		},
	},
};

export const CloudRun: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "cloud-run",
		},
	},
};

export const CloudRunV2: Story = {
	args: {
		workPool: {
			...createFakeWorkPool(),
			type: "cloud-run-v2",
		},
	},
};
