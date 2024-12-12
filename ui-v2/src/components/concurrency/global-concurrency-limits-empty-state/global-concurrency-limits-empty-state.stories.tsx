import type { Meta, StoryObj } from "@storybook/react";
import { GlobalConcurrencyLimitsEmptyState } from "./global-concurrency-limits-empty-state";

export const story: StoryObj = { name: "GlobalConcurrencyLimitsEmptyState" };

export default {
	title: "Components/Concurrency/GlobalConcurrencyLimitsEmptyState",
	component: GlobalConcurrencyLimitsEmptyState,
	args: {
		onAdd: () => {},
	},
} satisfies Meta;
