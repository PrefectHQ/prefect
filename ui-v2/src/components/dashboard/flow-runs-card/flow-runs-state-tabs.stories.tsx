import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import type { components } from "@/api/prefect";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunStateTabs } from "./flow-runs-state-tabs";

type StateType = components["schemas"]["StateType"];

export const story: StoryObj = { name: "FlowRunStateTabs" };

export default {
	title: "Dashboard/FlowRunStateTabs",
	component: function FlowRunStateTabsStories() {
		const [selectedStates, setSelectedStates] = useState<StateType[]>([
			"FAILED",
			"CRASHED",
		]);

		// Create sample flow runs with different states
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "SCHEDULED" }),
			createFakeFlowRun({ state_type: "CANCELLED" }),
		];

		// Filter flow runs based on selected states
		const filteredFlowRuns = flowRuns.filter((run) =>
			selectedStates.includes(run.state_type as StateType),
		);

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
					flowRuns={flowRuns}
					selectedStates={selectedStates}
					onStateChange={handleStateChange}
				/>

				<div className="border rounded-lg p-4">
					<h3 className="text-sm font-medium mb-2">
						Filtered Flow Runs ({filteredFlowRuns.length})
					</h3>
					<div className="text-xs text-muted-foreground">
						Selected states: <strong>{selectedStates.join(", ")}</strong>
					</div>
					<div className="mt-4 space-y-2">
						{filteredFlowRuns.map((run) => (
							<div
								key={run.id}
								className="flex items-center gap-2 text-sm border-b pb-2"
							>
								<span className="font-mono text-xs text-muted-foreground">
									{run.name}
								</span>
								<span className="text-xs">→</span>
								<span className="text-xs">{run.state_type}</span>
							</div>
						))}
					</div>
				</div>

				<div className="border rounded-lg p-4 bg-muted/50">
					<h3 className="text-sm font-semibold mb-2">Component Details</h3>
					<ul className="text-xs space-y-1 text-muted-foreground">
						<li>• Total flow runs: {flowRuns.length}</li>
						<li>
							• Completed:{" "}
							{flowRuns.filter((r) => r.state_type === "COMPLETED").length}
						</li>
						<li>
							• Failed:{" "}
							{flowRuns.filter((r) => r.state_type === "FAILED").length}
						</li>
						<li>
							• Running:{" "}
							{flowRuns.filter((r) => r.state_type === "RUNNING").length}
						</li>
						<li>
							• Scheduled:{" "}
							{flowRuns.filter((r) => r.state_type === "SCHEDULED").length}
						</li>
						<li>
							• Cancelled:{" "}
							{flowRuns.filter((r) => r.state_type === "CANCELLED").length}
						</li>
					</ul>
				</div>
			</div>
		);
	},
} satisfies Meta;
