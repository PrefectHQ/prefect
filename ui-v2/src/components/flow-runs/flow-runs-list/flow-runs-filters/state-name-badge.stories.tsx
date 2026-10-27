import type { Meta, StoryObj } from "@storybook/react";
import { StateNameBadge } from "./state-name-badge";

const meta = {
	title: "Components/FlowRuns/StateNameBadge",
	component: StateNameBadge,
} satisfies Meta<typeof StateNameBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BuiltIn: Story = { args: { name: "Failed" } };
export const Cached: Story = { args: { name: "Cached" } };
export const Custom: Story = { args: { name: "Baseline, NOT Met" } };
