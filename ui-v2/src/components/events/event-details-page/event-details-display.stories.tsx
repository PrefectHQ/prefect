import type { Meta, StoryObj } from "@storybook/react";
import type { Event } from "@/api/events";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { EventDetailsDisplay } from "./event-details-display";

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
	received: new Date().toISOString(),
	...overrides,
});

const meta = {
	title: "Components/Events/EventDetailsDisplay",
	component: EventDetailsDisplay,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof EventDetailsDisplay>;

export default meta;
type Story = StoryObj<typeof EventDetailsDisplay>;

export const Default: Story = {
	args: {
		event: createMockEvent({
			id: "event-1",
			occurred: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
			event: "prefect.flow-run.Completed",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc123",
				"prefect.resource.name": "etl-pipeline-run-1",
			},
		}),
	},
};

export const WithRelatedResourcesAndTags: Story = {
	args: {
		event: createMockEvent({
			id: "event-2",
			occurred: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
			event: "prefect.flow-run.Completed",
			resource: {
				"prefect.resource.id": "prefect.flow-run.xyz789",
				"prefect.resource.name": "data-sync-run",
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
				{
					"prefect.resource.id": "prefect.work-pool.pool123",
					"prefect.resource.role": "work-pool",
					"prefect.resource.name": "default-pool",
				},
				{
					"prefect.resource.id": "prefect.tag.production",
					"prefect.resource.role": "tag",
				},
				{
					"prefect.resource.id": "prefect.tag.critical",
					"prefect.resource.role": "tag",
				},
				{
					"prefect.resource.id": "prefect.tag.etl",
					"prefect.resource.role": "tag",
				},
			],
			payload: {
				validated: true,
				duration: 120,
			},
		}),
	},
};

export const Minimal: Story = {
	args: {
		event: createMockEvent({
			id: "event-3",
			occurred: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
			event: "prefect.task-run.Running",
			resource: {
				"prefect.resource.id": "prefect.task-run.task123",
				"prefect.resource.name": "extract-data",
			},
			related: [],
		}),
	},
};
