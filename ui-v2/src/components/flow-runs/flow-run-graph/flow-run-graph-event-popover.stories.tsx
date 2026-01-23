import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphEventPopover } from "./flow-run-graph-event-popover";

const meta = {
	component: FlowRunGraphEventPopover,
	title: "Components/FlowRuns/FlowRunGraphEventPopover",
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof FlowRunGraphEventPopover>;

export default meta;

type Story = StoryObj<typeof meta>;

const createEventSelection = (
	id: string,
	occurred: Date = new Date("2024-01-15T10:30:00Z"),
) => ({
	kind: "event" as const,
	id,
	occurred,
	position: { x: 200, y: 100, width: 20, height: 20 },
});

const createMockEventResponse = (
	id: string,
	eventName: string,
	resourceName: string,
	occurred = "2024-01-15T10:30:00Z",
) => ({
	events: [
		{
			id,
			occurred,
			received: occurred,
			event: eventName,
			resource: {
				"prefect.resource.id": `prefect.flow-run.${id}`,
				"prefect.resource.name": resourceName,
			},
			payload: {},
			related: [],
		},
	],
	total: 1,
	next_page: null,
});

export const Default: Story = {
	args: {
		selection: createEventSelection("event-001"),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse(
							"event-001",
							"prefect.flow-run.completed",
							"my-flow-run",
						),
					);
				}),
			],
		},
	},
};

export const FlowRunStarted: Story = {
	args: {
		selection: createEventSelection("event-002"),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse(
							"event-002",
							"prefect.flow-run.started",
							"data-pipeline",
						),
					);
				}),
			],
		},
	},
};

export const FlowRunFailed: Story = {
	args: {
		selection: createEventSelection("event-003"),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse(
							"event-003",
							"prefect.flow-run.failed",
							"etl-workflow",
						),
					);
				}),
			],
		},
	},
};

export const DeploymentEvent: Story = {
	args: {
		selection: createEventSelection("event-004"),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse(
							"event-004",
							"prefect.deployment.created",
							"my-deployment",
						),
					);
				}),
			],
		},
	},
};

export const CustomEvent: Story = {
	args: {
		selection: createEventSelection("event-005"),
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(
						createMockEventResponse(
							"event-005",
							"custom.data-quality.check-passed",
							"quality-monitor",
						),
					);
				}),
			],
		},
	},
};
