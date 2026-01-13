import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeBlockDocument, createFakeBlockType } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { BlockDocumentCombobox } from "./block-document-combobox";

const MOCK_BLOCK_TYPE = createFakeBlockType({
	slug: "test-block-type",
	name: "Test Block",
});

const MOCK_BLOCK_DOCUMENTS = Array.from({ length: 5 }, (_, i) =>
	createFakeBlockDocument({ name: `test-block-${i}` }),
);

const meta = {
	title: "Components/Blocks/BlockDocumentCombobox",
	render: () => <BlockDocumentComboboxStory />,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/block_types/slug/:slug"), () => {
					return HttpResponse.json(MOCK_BLOCK_TYPE);
				}),
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json(MOCK_BLOCK_DOCUMENTS);
				}),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "BlockDocumentCombobox" };

const BlockDocumentComboboxStory = () => {
	const [selected, setSelected] = useState<string | undefined>();

	return (
		<BlockDocumentCombobox
			blockTypeSlug="test-block-type"
			selectedBlockDocumentId={selected}
			onSelect={setSelected}
			onCreateNew={() => alert("Create new clicked")}
		/>
	);
};
