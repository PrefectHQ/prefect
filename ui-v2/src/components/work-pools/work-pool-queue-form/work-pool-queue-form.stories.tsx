import type { Meta, StoryObj } from "@storybook/react";
import { createFakeWorkPoolQueue } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolQueueForm } from "./work-pool-queue-form";

const meta: Meta<typeof WorkPoolQueueForm> = {
	title: "Components/WorkPools/WorkPoolQueueForm",
	component: WorkPoolQueueForm,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueueForm>;

export const Create: Story = {
	args: {
		workPoolName: "my-work-pool",
		onSubmit: () => {},
		onCancel: () => {},
	},
};

export const Edit: Story = {
	args: {
		workPoolName: "my-work-pool",
		onSubmit: () => {},
		onCancel: () => {},
		queueToEdit: createFakeWorkPoolQueue({
			name: "my-queue",
			description: "A test work queue for processing data",
			concurrency_limit: 10,
			priority: 2,
			work_pool_name: "my-work-pool",
		}),
	},
};

export const EditWithNullValues: Story = {
	args: {
		workPoolName: "my-work-pool",
		onSubmit: () => {},
		onCancel: () => {},
		queueToEdit: createFakeWorkPoolQueue({
			name: "minimal-queue",
			description: null,
			concurrency_limit: null,
			priority: undefined,
			work_pool_name: "my-work-pool",
		}),
	},
};
