import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

const meta = {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsHeader",
	component: GlobalConcurrencyLimitsHeader,
	args: { onAdd: fn() },
} satisfies Meta<typeof GlobalConcurrencyLimitsHeader>;

export default meta;

export const Story: StoryObj = {
	name: "GlobalConcurrencyLimitsHeader",
};
