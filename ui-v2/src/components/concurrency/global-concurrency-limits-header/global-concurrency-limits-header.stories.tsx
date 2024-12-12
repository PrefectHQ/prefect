import type { Meta, StoryObj } from "@storybook/react";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

const meta = {
	title: "Components/Concurrency/GlobalConcurrencyLimitsHeader",
	component: GlobalConcurrencyLimitsHeader,
	args: {
		onAdd: () => {},
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsHeader>;

export default meta;

export const Story: StoryObj = {
	name: "GlobalConcurrencyLimitsHeader",
};
