import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { toastDecorator } from "@/storybook/utils/toast-decorator";
import { WorkPoolQueueCreateDialog } from "./work-pool-queue-create-dialog";

const meta: Meta<typeof WorkPoolQueueCreateDialog> = {
	title: "Components/WorkPools/WorkPoolQueueCreateDialog",
	component: WorkPoolQueueCreateDialog,
	decorators: [toastDecorator, reactQueryDecorator],
	args: {
		workPoolName: "my-work-pool",
		open: true,
		onOpenChange: fn(),
		onSubmit: fn(),
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueueCreateDialog>;

export const Default: Story = {};

export const Closed: Story = {
	args: {
		open: false,
	},
};

export const WithLongWorkPoolName: Story = {
	args: {
		workPoolName: "very-long-work-pool-name-that-might-cause-layout-issues",
	},
};
