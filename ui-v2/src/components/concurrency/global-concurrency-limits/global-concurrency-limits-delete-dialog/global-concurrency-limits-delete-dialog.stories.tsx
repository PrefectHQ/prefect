import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeGlobalConcurrencyLimit } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { GlobalConcurrencyLimitsDeleteDialog } from "./global-concurrency-limits-delete-dialog";

const meta = {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsDeleteDialog",
	component: GlobalConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		limit: createFakeGlobalConcurrencyLimit(),
		onOpenChange: fn(),
		onDelete: fn(),
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "GlobalConcurrencyLimitsDeleteDialog" };
