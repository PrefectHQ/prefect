import { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import DemoData from "./demo-data.json";
import DemoEvents from "./demo-events.json";
import { RunGraph } from "./flow-run-graph";

const meta = {
	component: RunGraph,
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
} satisfies Meta<typeof RunGraph>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowRunId: "foo",
	},
};
