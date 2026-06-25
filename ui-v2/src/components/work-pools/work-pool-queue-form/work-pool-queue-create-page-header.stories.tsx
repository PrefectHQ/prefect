import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolQueueCreatePageHeader } from "./work-pool-queue-create-page-header";

const meta: Meta<typeof WorkPoolQueueCreatePageHeader> = {
	title: "Components/WorkPools/WorkPoolQueueCreatePageHeader",
	component: WorkPoolQueueCreatePageHeader,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueueCreatePageHeader>;

export const Default: Story = {
	args: {
		workPoolName: "my-work-pool",
	},
};

export const LongName: Story = {
	args: {
		workPoolName:
			"very-long-work-pool-name-that-might-wrap-or-truncate-in-the-breadcrumb",
	},
};

export const ShortName: Story = {
	args: {
		workPoolName: "dev",
	},
};
