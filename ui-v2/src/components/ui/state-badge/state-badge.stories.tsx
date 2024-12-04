import type { components } from "@/api/prefect.ts";
import type { Meta, StoryObj } from "@storybook/react";
import { StateBadge } from ".";

const badgesByState: Record<components["schemas"]["StateType"], string[]> = {
	COMPLETED: ["Completed"],
	FAILED: ["Failed"],
	RUNNING: ["Running"],
	PENDING: ["Pending"],
	PAUSED: ["Paused"],
	CANCELLED: ["Cancelled"],
	CANCELLING: ["Cancelling"],
	CRASHED: ["Crashed"],
	SCHEDULED: ["Scheduled", "Late"],
};

const meta = {
	title: "UI/StateBadge",
	component: function StateBadgeStories() {
		return (
			<div className="flex flex-col gap-4 items-start">
				{Object.entries(badgesByState).map(([type, names]) =>
					names.map((name) => (
						<StateBadge
							key={name}
							state={{ type, name } as components["schemas"]["State"]}
						/>
					)),
				)}
			</div>
		);
	},
} satisfies Meta<typeof StateBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {};
