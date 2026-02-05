import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeBlockDocument } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { BlockDocumentCombobox } from "./block-document-combobox";

const MOCK_BLOCK_DOCUMENTS_DATA = Array.from({ length: 5 }, (_, i) =>
	createFakeBlockDocument({ name: `my-block-${i}` }),
);

const meta = {
	title: "Components/Blocks/BlockDocumentCombobox",
	render: (args) => <BlockDocumentComboboxStory {...args} />,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json(MOCK_BLOCK_DOCUMENTS_DATA);
				}),
			],
		},
	},
	args: {
		blockTypeSlug: "aws-credentials",
	},
} satisfies Meta<{ blockTypeSlug: string; showCreateNew?: boolean }>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = { name: "BlockDocumentCombobox" };

export const WithCreateNew: Story = {
	name: "With Create New Button",
	args: {
		showCreateNew: true,
	},
};

export const Empty: Story = {
	name: "Empty State",
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

const BlockDocumentComboboxStory = ({
	blockTypeSlug,
	showCreateNew,
}: {
	blockTypeSlug: string;
	showCreateNew?: boolean;
}) => {
	const [selected, setSelected] = useState<string | undefined>();

	return (
		<BlockDocumentCombobox
			blockTypeSlug={blockTypeSlug}
			selectedBlockDocumentId={selected}
			onSelect={setSelected}
			onCreateNew={
				showCreateNew ? () => alert("Create new clicked") : undefined
			}
		/>
	);
};
