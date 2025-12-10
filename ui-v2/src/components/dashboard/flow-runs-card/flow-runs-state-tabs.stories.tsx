import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import type { components } from "@/api/prefect";
import { FlowRunStateTabs, type StateTypeCounts } from "./flow-runs-state-tabs";

type StateType = components["schemas"]["StateType"];

export const story: StoryObj = { name: "FlowRunStateTabs" };

export default {
	title: "Dashboard/FlowRunStateTabs",
	component: function FlowRunStateTabsStories() {
		const [selectedStates, setSelectedStates] = useState<StateType[]>([
			"FAILED",
			"CRASHED",
		]);

		// Create sample state counts (simulating what would come from the count API)
		const stateCounts: StateTypeCounts = {
			COMPLETED: 3,
			FAILED: 2,
			CRASHED: 0,
			RUNNING: 4,
			PENDING: 0,
			CANCELLING: 0,
			SCHEDULED: 1,
			PAUSED: 0,
			CANCELLED: 1,
		};

		const handleStateChange = (states: StateType[]) => {
			setSelectedStates(states);
		};

		return (
			<div className="flex flex-col gap-6 p-6">
				<div>
					<h2 className="text-lg font-semibold mb-2">
						FlowRunStateTabs Component
					</h2>
					<p className="text-sm text-muted-foreground mb-4">
						Interactive tabs for filtering flow runs by state type. Click a tab
						to filter the list below.
					</p>
				</div>

				<FlowRunStateTabs
					stateCounts={stateCounts}
					selectedStates={selectedStates}
					onStateChange={handleStateChange}
				/>

				<div className="border rounded-lg p-4">
					<h3 className="text-sm font-medium mb-2">Selected States</h3>
					<div className="text-xs text-muted-foreground">
						Selected states: <strong>{selectedStates.join(", ")}</strong>
					</div>
				</div>

				<div className="border rounded-lg p-4 bg-muted/50">
					<h3 className="text-sm font-semibold mb-2">Component Details</h3>
					<ul className="text-xs space-y-1 text-muted-foreground">
						<li>
							• Total flow runs:{" "}
							{Object.values(stateCounts).reduce((a, b) => a + b, 0)}
						</li>
						<li>• Completed: {stateCounts.COMPLETED}</li>
						<li>
							• Failed + Crashed: {stateCounts.FAILED + stateCounts.CRASHED}
						</li>
						<li>
							• Running + Pending + Cancelling:{" "}
							{stateCounts.RUNNING +
								stateCounts.PENDING +
								stateCounts.CANCELLING}
						</li>
						<li>
							• Scheduled + Paused: {stateCounts.SCHEDULED + stateCounts.PAUSED}
						</li>
						<li>• Cancelled: {stateCounts.CANCELLED}</li>
					</ul>
				</div>
			</div>
		);
	},
} satisfies Meta;
