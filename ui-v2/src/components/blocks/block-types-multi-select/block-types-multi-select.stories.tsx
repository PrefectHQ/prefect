import { useSet } from "@/hooks/use-set";
import { createFakeBlockType } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
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
	const [selectedBlockTypesIds, { toggle, remove }] = useSet<string>();

	return (
		<BlockTypesMultiSelect
			selectedBlockTypesIds={selectedBlockTypesIds}
			onRemoveBlockType={remove}
			onToggleBlockType={toggle}
		/>
	);
}
