import type { Meta, StoryObj } from "@storybook/react";
import type { components } from "@/api/prefect";
import { StatusBadge } from "./index";

const statuses = ["READY", "NOT_READY", "PAUSED"] as const satisfies (
	| components["schemas"]["DeploymentStatus"]
	| components["schemas"]["WorkPoolStatus"]
)[];

const meta = {
	title: "UI/StatusBadge",
	component: function StatusBadgeStories() {
		return (
			<div className="flex flex-col gap-4 items-start">
				{statuses.map((status) => (
					<StatusBadge key={status} status={status} />
				))}
			</div>
		);
	},
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof StatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	name: "StatusBadge",
	args: {
		status: "Active",
	},
};
