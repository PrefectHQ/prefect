import { routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { BlocksEmptyState } from "./empty-state";

export const story: StoryObj = { name: "EmptyState" };

export default {
	component: BlocksEmptyState,
	title: "Components/Blocks/EmptyState",
	decorators: [routerDecorator],
} satisfies Meta;
