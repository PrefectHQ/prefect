import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeFlowRun } from "@/mocks/create-fake-flow-run";
import { createFakeTaskRun } from "@/mocks/create-fake-task-run";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphSelectionPanel } from "./flow-run-graph-selection-panel";

const mockTaskRun = createFakeTaskRun({
	id: "task-run-123",
	name: "extract-data-abc",
	tags: ["production", "etl"],
	total_run_time: 125,
	estimated_run_time: 130,
});

const mockFlowRun = createFakeFlowRun({
	id: "flow-run-456",
	name: "daily-pipeline-xyz",
	tags: ["scheduled", "critical"],
	total_run_time: 3600,
	estimated_run_time: 3500,
});

const meta = {
	title: "Components/FlowRuns/FlowRunGraph/SelectionPanel",
	component: FlowRunGraphSelectionPanel,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
	},
	argTypes: {
		onClose: { action: "onClose" },
	},
} satisfies Meta<typeof FlowRunGraphSelectionPanel>;

export default meta;

type Story = StoryObj<typeof meta>;

export const TaskRunSelection: Story = {
	args: {
		selection: { kind: "task-run", id: "task-run-123" },
		onClose: () => {},
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(mockTaskRun);
				}),
			],
		},
	},
	decorators: [
		(Story) => (
			<div className="relative w-96 h-96 bg-muted">
				<Story />
			</div>
		),
	],
};

export const FlowRunSelection: Story = {
	args: {
		selection: { kind: "flow-run", id: "flow-run-456" },
		onClose: () => {},
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(mockFlowRun);
				}),
			],
		},
	},
	decorators: [
		(Story) => (
			<div className="relative w-96 h-96 bg-muted">
				<Story />
			</div>
		),
	],
};
