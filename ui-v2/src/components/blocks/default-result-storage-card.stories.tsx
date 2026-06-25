import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import { createFakeBlockDocument } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { DefaultResultStorageCard } from "./default-result-storage-card";

const storageBlockDocument = createFakeBlockDocument({
	id: "fbb69463-262e-494a-8fff-362482ab3efd",
	name: "s3-results",
	block_type_name: "S3 Bucket",
	block_type: {
		id: "93e948b4-9a7e-4194-936c-3dd4fe2009ee",
		created: "2026-05-03T00:00:00Z",
		updated: "2026-05-03T00:00:00Z",
		name: "S3 Bucket",
		slug: "s3-bucket",
		logo_url: null,
		documentation_url: null,
		description: null,
		code_example: null,
		is_protected: false,
	},
});

const MOCK_STORAGE_BLOCKS = [
	storageBlockDocument,
	createFakeBlockDocument({ name: "gcs-results" }),
	createFakeBlockDocument({ name: "azure-results" }),
];

const meta = {
	title: "Components/Blocks/DefaultResultStorageCard",
	component: DefaultResultStorageCard,
	decorators: [reactQueryDecorator, toastDecorator, routerDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json(MOCK_STORAGE_BLOCKS);
				}),
			],
		},
	},
	args: {
		defaultResultStorageBlockId: storageBlockDocument.id,
		defaultResultStorageBlock: storageBlockDocument,
		onUpdateDefaultResultStorage: fn(),
		onClearDefaultResultStorage: fn(),
		isUpdatingDefaultResultStorage: false,
		isClearingDefaultResultStorage: false,
		isLoadingDefaultResultStorageBlock: false,
	},
} satisfies Meta<typeof DefaultResultStorageCard>;

export default meta;

export const story: StoryObj = { name: "DefaultResultStorageCard" };

export const NotConfigured: StoryObj<typeof DefaultResultStorageCard> = {
	args: {
		defaultResultStorageBlockId: undefined,
		defaultResultStorageBlock: undefined,
	},
};

export const LoadingConfiguredBlock: StoryObj<typeof DefaultResultStorageCard> =
	{
		args: {
			defaultResultStorageBlockId: storageBlockDocument.id,
			defaultResultStorageBlock: undefined,
			isLoadingDefaultResultStorageBlock: true,
		},
	};
