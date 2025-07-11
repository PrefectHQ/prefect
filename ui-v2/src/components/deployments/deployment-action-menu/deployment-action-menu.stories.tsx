import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { routerDecorator, toastDecorator } from "@/storybook/utils";

import { DeploymentActionMenu } from "./deployment-action-menu";

const meta = {
	title: "Components/Deployments/DeploymentActionMenu",
	component: DeploymentActionMenu,
	decorators: [toastDecorator, routerDecorator],
	args: {
		id: "my-id",
		onDelete: fn(),
	},
} satisfies Meta<typeof DeploymentActionMenu>;

export default meta;

export const story: StoryObj = { name: "DeploymentActionMenu" };
