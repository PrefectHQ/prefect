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
