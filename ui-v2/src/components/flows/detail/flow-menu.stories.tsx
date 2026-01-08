import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeFlow } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { FlowMenu } from "./flow-menu";

const meta = {
	title: "Components/Flows/FlowMenu",
	component: FlowMenu,
	decorators: [toastDecorator, routerDecorator],
	args: {
		flow: createFakeFlow({ name: "my-test-flow" }),
		onDelete: fn(),
	},
} satisfies Meta<typeof FlowMenu>;

export default meta;

export const story: StoryObj = { name: "FlowMenu" };
