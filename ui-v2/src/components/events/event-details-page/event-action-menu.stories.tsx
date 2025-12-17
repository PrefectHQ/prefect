import type { Meta, StoryObj } from "@storybook/react";
import { createFakeEvent } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { EventActionMenu } from "./event-action-menu";

const meta = {
	title: "Components/Events/EventActionMenu",
	component: EventActionMenu,
	decorators: [toastDecorator, routerDecorator],
	args: {
		event: createFakeEvent(),
	},
} satisfies Meta<typeof EventActionMenu>;

export default meta;

export const story: StoryObj = { name: "EventActionMenu" };
