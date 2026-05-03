import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeBlockDocument } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
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

const meta = {
	title: "Components/Blocks/DefaultResultStorageCard",
	component: DefaultResultStorageCard,
	decorators: [toastDecorator, routerDecorator],
	args: {
		defaultResultStorageBlockId: storageBlockDocument.id,
		defaultResultStorageBlock: storageBlockDocument,
		storageBlockDocuments: [storageBlockDocument],
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
