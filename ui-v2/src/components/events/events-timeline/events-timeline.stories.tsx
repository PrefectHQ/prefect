import type { Meta, StoryObj } from "@storybook/react";
import type { components } from "@/api/prefect";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { EventsTimeline } from "./events-timeline";

type Event = components["schemas"]["ReceivedEvent"];

const createMockEvent = (overrides: Partial<Event> = {}): Event => ({
	id: crypto.randomUUID(),
	occurred: new Date().toISOString(),
	event: "prefect.flow-run.Completed",
	resource: {
		"prefect.resource.id": `prefect.flow-run.${crypto.randomUUID()}`,
		"prefect.resource.name": "my-flow-run",
	},
	related: [],
	payload: {},
	...overrides,
});

const MOCK_EVENTS: Event[] = [
	createMockEvent({
		id: "event-1",
		occurred: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 minutes ago
		event: "prefect.flow-run.Completed",
		resource: {
			"prefect.resource.id": "prefect.flow-run.abc123",
			"prefect.resource.name": "etl-pipeline-run-1",
		},
		related: [
			{
				"prefect.resource.id": "prefect.flow.def456",
				"prefect.resource.role": "flow",
				"prefect.resource.name": "etl-pipeline",
			},
			{
				"prefect.resource.id": "prefect.deployment.ghi789",
				"prefect.resource.role": "deployment",
				"prefect.resource.name": "production-deployment",
			},
		],
		payload: {
			validated: true,
			duration: 120,
		},
	}),
	createMockEvent({
		id: "event-2",
		occurred: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 minutes ago
		event: "prefect.flow-run.Failed",
		resource: {
			"prefect.resource.id": "prefect.flow-run.xyz789",
			"prefect.resource.name": "data-sync-run-2",
		},
		related: [
			{
				"prefect.resource.id": "prefect.tag.production",
				"prefect.resource.role": "tag",
			},
			{
				"prefect.resource.id": "prefect.tag.critical",
				"prefect.resource.role": "tag",
			},
		],
		payload: {
			error: "Connection timeout",
		},
	}),
	createMockEvent({
		id: "event-3",
		occurred: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
		event: "prefect.task-run.Running",
		resource: {
			"prefect.resource.id": "prefect.task-run.task123",
			"prefect.resource.name": "extract-data",
		},
		related: [],
	}),
	createMockEvent({
		id: "event-4",
		occurred: new Date(Date.now() - 1000 * 60 * 60).toISOString(), // 1 hour ago
		event: "prefect.deployment.Created",
		resource: {
			"prefect.resource.id": "prefect.deployment.deploy123",
			"prefect.resource.name": "new-deployment",
		},
		related: [
			{
				"prefect.resource.id": "prefect.flow.flow456",
				"prefect.resource.role": "flow",
				"prefect.resource.name": "my-flow",
			},
		],
	}),
];

const meta = {
	title: "Components/Events/EventsTimeline",
	component: EventsTimeline,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof EventsTimeline>;

export default meta;
type Story = StoryObj<typeof EventsTimeline>;

export const Default: Story = {
	args: {
		events: MOCK_EVENTS,
	},
};

export const SingleEvent: Story = {
	args: {
		events: [MOCK_EVENTS[0]],
	},
};

export const Empty: Story = {
	args: {
		events: [],
	},
};

export const WithTags: Story = {
	args: {
		events: [
			createMockEvent({
				id: "event-with-tags",
				event: "prefect.flow-run.Completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.tagged-run",
					"prefect.resource.name": "tagged-flow-run",
				},
				related: [
					{
						"prefect.resource.id": "prefect.tag.production",
						"prefect.resource.role": "tag",
					},
					{
						"prefect.resource.id": "prefect.tag.etl",
						"prefect.resource.role": "tag",
					},
					{
						"prefect.resource.id": "prefect.tag.daily",
						"prefect.resource.role": "tag",
					},
					{
						"prefect.resource.id": "prefect.flow.my-flow",
						"prefect.resource.role": "flow",
						"prefect.resource.name": "my-flow",
					},
				],
			}),
		],
	},
};

export const MixedEventTypes: Story = {
	args: {
		events: [
			createMockEvent({
				id: "completed",
				event: "prefect.flow-run.Completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.1",
					"prefect.resource.name": "completed-run",
				},
			}),
			createMockEvent({
				id: "failed",
				event: "prefect.flow-run.Failed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.2",
					"prefect.resource.name": "failed-run",
				},
			}),
			createMockEvent({
				id: "running",
				event: "prefect.task-run.Running",
				resource: {
					"prefect.resource.id": "prefect.task-run.3",
					"prefect.resource.name": "running-task",
				},
			}),
			createMockEvent({
				id: "scheduled",
				event: "prefect.flow-run.Scheduled",
				resource: {
					"prefect.resource.id": "prefect.flow-run.4",
					"prefect.resource.name": "scheduled-run",
				},
			}),
		],
	},
};
