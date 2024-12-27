import {
	createFakeGlobalConcurrencyLimit,
	reactQueryDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { GlobalConcurrencyLimitsDeleteDialog } from "./global-concurrency-limits-delete-dialog";

const meta = {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsDeleteDialog",
	component: GlobalConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator],
	args: {
		limit: createFakeGlobalConcurrencyLimit(),
		onOpenChange: () => {},
		onDelete: () => {},
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "GlobalConcurrencyLimitsDeleteDialog" };
