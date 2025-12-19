import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { toastDecorator } from "@/storybook/utils/toast-decorator";
import { WorkPoolQueueCreateOrEditDialog } from "./work-pool-queue-create-dialog";

const meta: Meta<typeof WorkPoolQueueCreateOrEditDialog> = {
	title: "Components/WorkPools/WorkPoolQueueCreateOrEditDialog",
	component: WorkPoolQueueCreateOrEditDialog,
	decorators: [toastDecorator, reactQueryDecorator],
	args: {
		workPoolName: "my-work-pool",
		open: true,
		onOpenChange: fn(),
		onSubmit: fn(),
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueueCreateOrEditDialog>;

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
