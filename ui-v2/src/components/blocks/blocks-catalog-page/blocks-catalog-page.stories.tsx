import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { BLOCK_TYPES } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { BlocksCatalogPage } from "./blocks-catalog-page";

const meta = {
	title: "Components/Blocks/BlocksCatalogPage",
	component: BlocksCatalogPage,
	decorators: [toastDecorator, routerDecorator],
	args: { blockTypes: BLOCK_TYPES, search: "", onSearch: fn() },
} satisfies Meta<typeof BlocksCatalogPage>;

export default meta;

export const story: StoryObj = { name: "BlocksCatalogPage" };
