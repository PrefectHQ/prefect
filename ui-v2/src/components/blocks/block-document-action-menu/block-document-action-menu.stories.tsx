import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeBlockDocument } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { BlockDocumentActionMenu } from "./block-document-action-menu";

const meta = {
	title: "Components/Blocks/BlockDocumentActionMenu",
	component: BlockDocumentActionMenu,
	decorators: [toastDecorator, routerDecorator],
	args: {
		blockDocument: createFakeBlockDocument(),
		onDelete: fn(),
	},
} satisfies Meta<typeof BlockDocumentActionMenu>;

export default meta;

export const story: StoryObj = { name: "BlockDocumentActionMenu" };
