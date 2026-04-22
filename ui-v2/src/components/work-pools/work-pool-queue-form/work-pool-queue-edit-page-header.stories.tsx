import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolQueueEditPageHeader } from "./work-pool-queue-edit-page-header";

const meta: Meta<typeof WorkPoolQueueEditPageHeader> = {
	title: "Components/WorkPools/WorkPoolQueueEditPageHeader",
	component: WorkPoolQueueEditPageHeader,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueueEditPageHeader>;

export const Default: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "my-queue",
	},
};

export const LongNames: Story = {
	args: {
		workPoolName: "very-long-work-pool-name-that-might-truncate",
		workQueueName: "very-long-queue-name-that-might-truncate",
	},
};

export const ShortNames: Story = {
	args: {
		workPoolName: "dev",
		workQueueName: "q1",
	},
};
