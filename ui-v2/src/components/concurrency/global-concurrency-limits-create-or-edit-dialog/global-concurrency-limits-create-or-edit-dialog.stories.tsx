import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { GlobalConcurrencyLimitsCreateOrEditDialog } from "./global-concurrency-limits-create-or-edit-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	active: false,
	name: "global concurrency limit 0",
	limit: 0,
	active_slots: 0,
	slot_decay_per_second: 0,
};

const meta = {
	title: "Components/Concurrency/GlobalConcurrencyLimitsCreateOrEditDialog",
	component: GlobalConcurrencyLimitsCreateOrEditDialog,
	decorators: [reactQueryDecorator],
	args: {
		onOpenChange: () => {},
		onSubmit: () => {},
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsCreateOrEditDialog>;

export default meta;

type Story = StoryObj<typeof GlobalConcurrencyLimitsCreateOrEditDialog>;

export const CreateLimit: Story = {};

export const EditLimit: Story = {
	args: {
		limitToUpdate: MOCK_DATA,
	},
};
