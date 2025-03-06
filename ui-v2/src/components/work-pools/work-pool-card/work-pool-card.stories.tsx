import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolCard } from "./work-pool-card";

const meta: Meta<typeof WorkPoolCard> = {
	title: "Components/WorkPools/Card",
	component: WorkPoolCard,
	parameters: {},
};

export default meta;
type Story = StoryObj<typeof WorkPoolCard>;

export const Default: Story = {};
