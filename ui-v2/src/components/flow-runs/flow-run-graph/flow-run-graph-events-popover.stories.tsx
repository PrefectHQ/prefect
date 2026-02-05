import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphEventsPopover } from "./flow-run-graph-events-popover";

const meta = {
	component: FlowRunGraphEventsPopover,
	title: "Components/FlowRuns/FlowRunGraphEventsPopover",
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof FlowRunGraphEventsPopover>;

export default meta;

type Story = StoryObj<typeof meta>;

const createEventsSelection = (
	ids: string[],
	occurred: Date = new Date("2024-01-15T10:30:00Z"),
) => ({
	kind: "events" as const,
	ids,
	occurred,
	position: { x: 200, y: 100, width: 20, height: 20 },
});

const createMockEventResponse = (id: string, eventName: string) => ({
	events: [
		{
			id,
			occurred: "2024-01-15T10:30:00Z",
			received: "2024-01-15T10:30:01Z",
			event: eventName,
			resource: {
				"prefect.resource.id": `prefect.flow-run.${id}`,
				"prefect.resource.name": "my-flow-run",
			},
			payload: {},
			related: [],
		},
	],
	total: 1,
	next_page: null,
});

export const TwoEvents: Story = {
	args: {
		selection: createEventsSelection(["event-1", "event-2"]),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse("event-1", "prefect.flow-run.started"),
					);
				}),
			],
		},
	},
};

export const MultipleEvents: Story = {
	args: {
		selection: createEventsSelection([
			"event-1",
			"event-2",
			"event-3",
			"event-4",
			"event-5",
		]),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse("event-1", "prefect.flow-run.completed"),
					);
				}),
			],
		},
	},
};
