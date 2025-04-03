import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import { FlowRunStateDialog } from "./flow-run-state-dialog";
import { useFlowRunStateDialog } from "./use-flow-run-state-dialog";

// Create a base mock flow run with only the required properties
type MockFlowRun = Pick<FlowRun, "id" | "name" | "state">;

const createMockFlowRun = (
	overrides: Partial<MockFlowRun> = {},
): MockFlowRun => ({
	id: "mock-flow-run-id",
	name: "Mock Flow Run",
	state: undefined,
	...overrides,
});

// Mock flow run with COMPLETED state
const completedFlowRun = createMockFlowRun({
	id: "mock-flow-run-id-1",
	name: "Completed Flow Run",
	state: {
		id: "state-id-1",
		type: "COMPLETED" as components["schemas"]["StateType"],
		name: "Completed",
		timestamp: "2023-10-15T10:30:00Z",
		message: "Flow run completed successfully",
	},
}) as FlowRun;

// Mock flow run with FAILED state
const failedFlowRun = createMockFlowRun({
	id: "mock-flow-run-id-2",
	name: "Failed Flow Run",
	state: {
		id: "state-id-2",
		type: "FAILED" as components["schemas"]["StateType"],
		name: "Failed",
		timestamp: "2023-10-15T11:15:00Z",
		message: "Flow run failed with an error",
	},
}) as FlowRun;

// ------- Dialog Component Stories -------

const meta: Meta<typeof FlowRunStateDialog> = {
	title: "Components/FlowRuns/FlowRunStateDialog",
	component: FlowRunStateDialog,
	parameters: {
		layout: "centered",
	},
	decorators: [reactQueryDecorator, toastDecorator],
	argTypes: {},
};

export default meta;
type Story = StoryObj<typeof FlowRunStateDialog>;

// Base story configuration
const baseStory: Story = {
	args: {
		open: true,
		onOpenChange: fn(),
	},
	parameters: {
		docs: {
			description: {
				story: "Dialog for changing the state of a flow run",
			},
		},
	},
};

// Basic state stories showing different initial states
export const CompletedFlowRun: Story = {
	...baseStory,
	args: {
		...baseStory.args,
		flowRun: completedFlowRun,
	},
};

export const FailedFlowRun: Story = {
	...baseStory,
	args: {
		...baseStory.args,
		flowRun: failedFlowRun,
	},
};

// ------- Full Lifecycle Demo with Hook and Toast -------

// Component demonstrating the complete flow with automatic dialog close and toast notification
const FullLifecycleDemo = () => {
	const [dialogState, openDialog] = useFlowRunStateDialog();
	const [isOpen, setIsOpen] = useState(false);

	// Custom handler to track local state
	const handleOpenChange = (open: boolean) => {
		setIsOpen(open);
		dialogState.onOpenChange(open);
	};

	return (
		<div className="space-y-4">
			<div className="p-4 border rounded-lg">
				<h2 className="text-lg font-medium mb-2">Complete Flow Demo</h2>
				<p className="mb-4">
					This demonstrates the full lifecycle including toast notifications:
				</p>
				<ol className="list-decimal pl-6 mb-4 space-y-1">
					<li>Click the button to open the dialog</li>
					<li>Select a different state and submit the form</li>
					<li>The dialog will close</li>
					<li>A toast notification will appear showing the state change</li>
				</ol>
				<Button
					onClick={() => {
						openDialog(completedFlowRun);
						setIsOpen(true);
					}}
					disabled={isOpen}
				>
					Change Flow Run State
				</Button>
				{isOpen ? (
					<p className="text-sm text-muted-foreground mt-2">
						Dialog is open - complete the form to see toast notification
					</p>
				) : (
					<p className="text-sm text-muted-foreground mt-2">
						Dialog is closed - click the button to open it
					</p>
				)}
			</div>

			<FlowRunStateDialog
				{...dialogState}
				open={isOpen}
				onOpenChange={handleOpenChange}
			/>
		</div>
	);
};

// Demo that showcases success flow
export const SuccessDemo: StoryObj<typeof FullLifecycleDemo> = {
	name: "Success Flow with Toast",
	render: () => <FullLifecycleDemo />,
	parameters: {
		docs: {
			description: {
				story:
					"Shows the complete flow with successful state change and toast notification",
			},
		},
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/:id/set_state"), () => {
					return HttpResponse.json({ state: { type: "FAILED" } });
				}),
			],
		},
	},
};

// Demo that showcases error flow
export const ErrorDemo: StoryObj<typeof FullLifecycleDemo> = {
	name: "Error Flow with Toast",
	render: () => <FullLifecycleDemo />,
	parameters: {
		docs: {
			description: {
				story:
					"Shows the complete flow with error during state change and error toast",
			},
		},
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/:id/set_state"), () => {
					return HttpResponse.json(
						{
							detail: "Error: Unable to change flow run state - access denied",
						},
						{ status: 403 },
					);
				}),
			],
		},
	},
};
