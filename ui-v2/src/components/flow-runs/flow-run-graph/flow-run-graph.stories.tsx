import { TooltipProvider } from "@radix-ui/react-tooltip";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import type { ComponentProps } from "react";
import DemoData from "./demo-data.json";
import DemoEvents from "./demo-events.json";
import { FlowRunGraph } from "./flow-run-graph";

function Wrapper(props: ComponentProps<typeof FlowRunGraph>) {
	return (
		<TooltipProvider>
			<FlowRunGraph {...props} />
		</TooltipProvider>
	);
}

const meta = {
	component: Wrapper,
	title: "Components/FlowRuns/FlowRunGraph",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/foo/graph-v2"), () => {
					return HttpResponse.json(DemoData);
				}),
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(DemoEvents);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(5);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunGraph>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowRunId: "foo",
	},
};

export const EmptyStateTerminal: Story = {
	args: {
		flowRunId: "foo",
		stateType: "COMPLETED",
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/foo/graph-v2"), () => {
					return HttpResponse.json(DemoData);
				}),
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(DemoEvents);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			],
		},
	},
};

export const EmptyStateNonTerminal: Story = {
	args: {
		flowRunId: "foo",
		stateType: "RUNNING",
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/foo/graph-v2"), () => {
					return HttpResponse.json(DemoData);
				}),
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(DemoEvents);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			],
		},
	},
};
