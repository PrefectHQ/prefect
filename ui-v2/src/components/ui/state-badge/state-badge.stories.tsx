import type { Meta, StoryObj } from "@storybook/react";
import type { components } from "@/api/prefect.ts";
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

export const story: StoryObj = { name: "StateBadge" };

export default {
	title: "UI/StateBadge",
	component: function StateBadgeStories() {
		return (
			<div className="flex flex-col gap-4 items-start">
				{Object.entries(badgesByState).map(([type, names]) =>
					names.map((name) => (
						<StateBadge
							key={name}
							type={type as components["schemas"]["StateType"]}
							name={name}
						/>
					)),
				)}
			</div>
		);
	},
} satisfies Meta;
