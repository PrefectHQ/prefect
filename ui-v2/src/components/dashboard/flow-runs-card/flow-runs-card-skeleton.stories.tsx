import type { Meta, StoryObj } from "@storybook/react";
import { FlowRunsCardSkeleton } from "./flow-runs-card-skeleton";

const meta: Meta<typeof FlowRunsCardSkeleton> = {
	title: "Components/Dashboard/FlowRunsCardSkeleton",
	component: FlowRunsCardSkeleton,
	parameters: {
		docs: {
			description: {
				component:
					"FlowRunsCardSkeleton displays a loading placeholder for the FlowRunsCard component.",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};
