import { BlockDocument } from "@/api/block-documents";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { BlockDocumentsDataTable } from "./block-document-data-table";

const MOCK_BLOCK_DOCUMENT: BlockDocument = {
	id: "b0a54f2b-036a-4364-a5c2-12e8f1238dd",
	created: "2025-03-16T23:15:15.439735Z",
	updated: "2025-03-16T23:15:15.439761Z",
	name: "my-json",
	block_schema_id: "2d05d6bb-bc60-4351-b53a-bdf2e3507392",
	block_schema: {
		capabilities: [],
		version: "3.1.5",
		id: "2d05d6bb-bc60-4351-b53a-bdf2e3507392",
		created: "2024-12-02T18:19:07.924907Z",
		fields: {
			block_type_slug: "json",
			description:
				"A block that represents JSON. Deprecated, please use Variables to store JSON data instead.",
			properties: {
				value: {
					description: "A JSON-compatible value.",
					title: "Value",
				},
			},
			required: ["value"],
			secret_fields: [],
			title: "JSON",
			type: "object",
			block_schema_references: {},
		},
		checksum:
			"sha256:0f01d400eb1ebd964d491132cda72e6a6d843f8ce940397b3dba7be219852106",
		block_type_id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
		updated: "2024-12-02T18:19:07.924910Z",
		block_type: {
			documentation_url: "https://docs.prefect.io/latest/develop/blocks",
			slug: "json",
			name: "JSON",
			code_example:
				'Load a stored JSON value:\n```python\nfrom prefect.blocks.system import JSON\n\njson_block = JSON.load("BLOCK_NAME")\n```',
			id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
			logo_url:
				"https://cdn.sanity.io/images/3ugk85nk/production/4fcef2294b6eeb423b1332d1ece5156bf296ff96-48x48.png",
			description:
				"A block that represents JSON. Deprecated, please use Variables to store JSON data instead.",
			is_protected: true,
			created: "2024-12-02T18:19:07.922307Z",
			updated: "2024-12-02T18:19:08.003000Z",
		},
	},
	block_type_id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
	block_type_name: "JSON",
	block_type: {
		id: "a0d50399-39b7-44ea-a0b8-4c5e99388b8f",
		created: "2024-12-02T18:19:07.922307Z",
		updated: "2024-12-02T18:19:08.003000Z",
		name: "JSON",
		slug: "json",
		logo_url:
			"https://cdn.sanity.io/images/3ugk85nk/production/4fcef2294b6eeb423b1332d1ece5156bf296ff96-48x48.png",
		documentation_url: "https://docs.prefect.io/latest/develop/blocks",
		description:
			"A block that represents JSON. Deprecated, please use Variables to store JSON data instead.",
		code_example:
			'Load a stored JSON value:\n```python\nfrom prefect.blocks.system import JSON\n\njson_block = JSON.load("BLOCK_NAME")\n```',
		is_protected: true,
	},
	block_document_references: {},
	is_anonymous: false,
};

const meta = {
	title: "Components/Blocks/BlockDocumentsDataTable",
	component: BlockDocumentsDataTable,
	decorators: [toastDecorator, routerDecorator],
	args: {
		blockDocuments: [
			{ ...MOCK_BLOCK_DOCUMENT, id: "1" },
			{ ...MOCK_BLOCK_DOCUMENT, id: "2" },
		],
		blockDocumentsCount: 2,
		onPaginationChange: fn(),
		onDelete: fn(),
		pagination: {
			pageIndex: 0,
			pageSize: 10,
		},
		rowSelection: {},
		setRowSelection: fn(),
	},
} satisfies Meta<typeof BlockDocumentsDataTable>;

export default meta;

export const story: StoryObj = { name: "BlockDocumentsDataTable" };
