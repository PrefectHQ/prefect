import { createFakeDeployment } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { DeploymentsDataTable } from ".";

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
	decorators: [toastDecorator, routerDecorator],
} satisfies Meta<typeof DeploymentsDataTable>;

export const Default: StoryObj = {
	name: "Randomized Data",
	args: {
		deployments: Array.from({ length: 10 }, createFakeDeployment),
		onQuickRun: fn(),
		onCustomRun: fn(),
		onEdit: fn(),
		onDelete: fn(),
		onDuplicate: fn(),
	},
};

export const Empty: StoryObj = {
	name: "Empty",
	args: {
		deployments: [],
	},
};
