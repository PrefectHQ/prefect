import type { Meta, StoryObj } from "@storybook/react";
import { FlowRunStateBadge } from "./flow-run-state-badge";
import { FLOW_RUN_STATES } from "./flow-run-states";

export const story: StoryObj = { name: "FlowRunStateBadge" };

export default {
	title: "UI/FlowRunStateBadge",
	render: () => {
		return (
			<div className="flex flex-col gap-4 items-start">
				{FLOW_RUN_STATES.map((state) => (
					<FlowRunStateBadge key={state} state={state} />
				))}
			</div>
		);
	},
} satisfies Meta;
