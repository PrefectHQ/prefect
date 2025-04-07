import { BLOCK_TYPES } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { BlockTypeCard } from "./block-type-card";

const meta = {
	title: "Components/Blocks/BlockTypeCard",
	component: BlockTypeCardStory,
	decorators: [toastDecorator, routerDecorator],
} satisfies Meta<typeof BlockTypeCard>;

export default meta;

export const story: StoryObj = { name: "BlockTypeCard" };

function BlockTypeCardStory() {
	return (
		<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{BLOCK_TYPES.map((blockType) => (
				<BlockTypeCard key={blockType.id} blockType={blockType} />
			))}
		</div>
	);
}
