import type { Meta, StoryObj } from "@storybook/react";
import { DeploymentsEmptyState } from ".";

export default {
	title: "UI/Deployments/EmptyState",
	component: DeploymentsEmptyState,
	args: {},
} satisfies Meta<typeof DeploymentsEmptyState>;

type Story = StoryObj<typeof DeploymentsEmptyState>;

export const Default: Story = {};
