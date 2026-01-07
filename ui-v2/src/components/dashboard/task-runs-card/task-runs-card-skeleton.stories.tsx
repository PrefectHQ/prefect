import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunsCardSkeleton } from "./task-runs-card-skeleton";

const meta: Meta<typeof TaskRunsCardSkeleton> = {
	title: "Components/Dashboard/TaskRunsCardSkeleton",
	component: TaskRunsCardSkeleton,
	parameters: {
		docs: {
			description: {
				component:
					"TaskRunsCardSkeleton displays a loading placeholder for the TaskRunsCard component.",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};
