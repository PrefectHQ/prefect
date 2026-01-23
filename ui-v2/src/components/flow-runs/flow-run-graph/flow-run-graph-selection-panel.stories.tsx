import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeFlowRun, createFakeTaskRun } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphSelectionPanel } from "./flow-run-graph-selection-panel";

const meta = {
	component: FlowRunGraphSelectionPanel,
	title: "Components/FlowRuns/FlowRunGraphSelectionPanel",
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof FlowRunGraphSelectionPanel>;

export default meta;

type Story = StoryObj<typeof meta>;

const mockTaskRun = createFakeTaskRun({
	id: "task-run-123",
	name: "extract-data",
	tags: ["production", "etl"],
	total_run_time: 125,
	estimated_run_time: 125,
});

const mockFlowRun = createFakeFlowRun({
	id: "flow-run-456",
	name: "daily-pipeline",
	tags: ["scheduled", "critical"],
	total_run_time: 3600,
});

export const TaskRunSelection: Story = {
	args: {
		selection: { kind: "task-run", id: "task-run-123" },
		onClose: () => console.log("Close clicked"),
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
};

export const FlowRunSelection: Story = {
	args: {
		selection: { kind: "flow-run", id: "flow-run-456" },
		onClose: () => console.log("Close clicked"),
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
};
