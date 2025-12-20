import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeFlow } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { DeleteFlowDialog } from "./delete-flow-dialog";

const meta = {
	title: "Components/Flows/DeleteFlowDialog",
	component: DeleteFlowDialog,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
	args: {
		flow: createFakeFlow({ name: "my-test-flow" }),
		onOpenChange: fn(),
		onDeleted: fn(),
	},
} satisfies Meta<typeof DeleteFlowDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Open: Story = {
	args: {
		open: true,
	},
};

export const Closed: Story = {
	args: {
		open: false,
	},
};
