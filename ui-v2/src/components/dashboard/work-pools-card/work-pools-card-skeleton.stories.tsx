import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolsCardSkeleton } from "./work-pools-card-skeleton";

const meta: Meta<typeof WorkPoolsCardSkeleton> = {
	title: "Components/Dashboard/WorkPoolsCardSkeleton",
	component: WorkPoolsCardSkeleton,
	parameters: {
		docs: {
			description: {
				component:
					"WorkPoolsCardSkeleton displays a loading placeholder for the DashboardWorkPoolsCard component.",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};
