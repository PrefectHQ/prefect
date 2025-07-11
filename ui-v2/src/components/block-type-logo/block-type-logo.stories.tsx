import type { Meta, StoryObj } from "@storybook/react";
import { BLOCK_TYPES } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { BlockTypeLogo } from "./block-type-logo";

const meta = {
	title: "Components/Blocks/BlockTypeLogo",
	component: BlockTypeLogoStory,
	decorators: [toastDecorator, routerDecorator],
} satisfies Meta<typeof BlockTypeLogo>;

export default meta;

export const story: StoryObj = { name: "BlockTypeLogo" };

const UNIQUE_LOGO_URLS = new Set(
	BLOCK_TYPES.filter((blockType) => Boolean(blockType.logo_url)).map(
		(blockType) => blockType.logo_url,
	) as Array<string>,
);

function BlockTypeLogoStory() {
	return (
		<div className="flex flex-col gap-4">
			<div className="flex gap-2">
				{Array.from(UNIQUE_LOGO_URLS).map((logoUrl) => (
					<BlockTypeLogo key={logoUrl} logoUrl={logoUrl} size="sm" />
				))}
			</div>

			<div className="flex gap-2">
				{Array.from(UNIQUE_LOGO_URLS).map((logoUrl) => (
					<BlockTypeLogo key={logoUrl} logoUrl={logoUrl} size="lg" />
				))}
			</div>
		</div>
	);
}
