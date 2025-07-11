import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeBlockType } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { BlockTypesMultiSelect } from "./block-types-multi-select";

const MOCK_BLOCK_TYPES = Array.from({ length: 5 }, createFakeBlockType);

const meta = {
	title: "Components/Blocks/BlockTypesMultiSelect",
	component: BlockTypesMultiSelectStory,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/block_types/filter"), () => {
					return HttpResponse.json(MOCK_BLOCK_TYPES);
				}),
			],
		},
	},
} satisfies Meta<typeof BlockTypesMultiSelect>;

export default meta;

export const Story: StoryObj = {
	name: "BlockTypesMultiSelect",
};

function BlockTypesMultiSelectStory() {
	const [selectedBlockTypeSlugs, onSelectedBlockTypeSlugs] = useState<
		Array<string>
	>([]);

	const handleRemoveBlockTypeSlug = (id: string) => {
		onSelectedBlockTypeSlugs((curr) =>
			curr.filter((blockId) => blockId !== id),
		);
	};

	const handleToggleBlockTypeSlug = (id: string) => {
		if (selectedBlockTypeSlugs.includes(id)) {
			return handleRemoveBlockTypeSlug(id);
		}
		onSelectedBlockTypeSlugs((curr) => [...curr, id]);
	};

	return (
		<BlockTypesMultiSelect
			selectedBlockTypesSlugs={selectedBlockTypeSlugs}
			onRemoveBlockTypeSlug={handleRemoveBlockTypeSlug}
			onToggleBlockTypeSlug={handleToggleBlockTypeSlug}
		/>
	);
}
