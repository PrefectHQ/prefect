import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeGlobalConcurrencyLimit } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { GlobalConcurrencyLimitsCreateOrEditDialog } from "./global-concurrency-limits-create-or-edit-dialog";

const meta = {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsCreateOrEditDialog",
	component: GlobalConcurrencyLimitsCreateOrEditDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		onOpenChange: fn(),
		onSubmit: fn(),
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsCreateOrEditDialog>;

export default meta;

type Story = StoryObj<typeof GlobalConcurrencyLimitsCreateOrEditDialog>;

export const CreateLimit: Story = {};

export const EditLimit: Story = {
	args: {
		limitToUpdate: createFakeGlobalConcurrencyLimit(),
	},
};
