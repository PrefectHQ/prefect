import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { createFakeBlockSchema, createFakeBlockType } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { BlockDocumentCreateDialog } from "./block-document-create-dialog";

const MOCK_BLOCK_TYPE = createFakeBlockType({
	id: "block-type-1",
	slug: "secret",
	name: "Secret",
});

const MOCK_BLOCK_SCHEMA = createFakeBlockSchema();

const meta = {
	title: "Components/Blocks/BlockDocumentCreateDialog",
	render: (args) => <BlockDocumentCreateDialogStory {...args} />,
	decorators: [reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/block_types/slug/:slug"), () => {
					return HttpResponse.json(MOCK_BLOCK_TYPE);
				}),
				http.post(buildApiUrl("/block_schemas/filter"), () => {
					return HttpResponse.json([
						{ ...MOCK_BLOCK_SCHEMA, block_type_id: MOCK_BLOCK_TYPE.id },
					]);
				}),
				http.post(buildApiUrl("/block_documents/"), () => {
					return HttpResponse.json({
						id: "new-block-document-id",
						name: "test-block",
					});
				}),
			],
		},
	},
	args: {
		blockTypeSlug: "secret",
	},
} satisfies Meta<{ blockTypeSlug: string }>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = { name: "BlockDocumentCreateDialog" };

const BlockDocumentCreateDialogStory = ({
	blockTypeSlug,
}: {
	blockTypeSlug: string;
}) => {
	const [open, setOpen] = useState(false);

	return (
		<>
			<Button onClick={() => setOpen(true)}>Open Dialog</Button>
			<BlockDocumentCreateDialog
				open={open}
				onOpenChange={setOpen}
				blockTypeSlug={blockTypeSlug}
				onCreated={(id) => alert(`Created block document: ${id}`)}
			/>
		</>
	);
};
