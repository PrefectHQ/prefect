import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { GlobalConcurrencyLimitsDeleteDialog } from "./global-concurrency-limits-delete-dialog";

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
	title: "Components/Concurrency/GlobalConcurrencyLimitsDeleteDialog",
	component: GlobalConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator],
	args: {
		limit: MOCK_DATA,
		onOpenChange: () => {},
		onDelete: () => {},
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "GlobalConcurrencyLimitsDeleteDialog" };
