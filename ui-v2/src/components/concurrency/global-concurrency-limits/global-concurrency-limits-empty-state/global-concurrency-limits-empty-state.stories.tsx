import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { GlobalConcurrencyLimitsEmptyState } from "./global-concurrency-limits-empty-state";

export const story: StoryObj = { name: "GlobalConcurrencyLimitsEmptyState" };

export default {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsEmptyState",
	component: GlobalConcurrencyLimitsEmptyState,
	args: { onAdd: fn() },
} satisfies Meta;
