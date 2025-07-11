import type { Meta, StoryObj } from "@storybook/react";
import { createFakeBlockType } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { BlockTypePage } from "./block-type-page";

const meta = {
	title: "Components/Blocks/BlockTypePage",
	component: BlockTypePage,
	decorators: [toastDecorator, routerDecorator],
	args: { blockType: createFakeBlockType() },
} satisfies Meta<typeof BlockTypePage>;

export default meta;

export const story: StoryObj = { name: "BlockTypePage" };
