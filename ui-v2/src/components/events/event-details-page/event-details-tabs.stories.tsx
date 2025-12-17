import type { Meta, StoryObj } from "@storybook/react";
import { createFakeEvent } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { EventDetailsTabs } from "./event-details-tabs";

const meta = {
	title: "Components/Events/EventDetailsTabs",
	component: EventDetailsTabs,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof EventDetailsTabs>;

export default meta;
type Story = StoryObj<typeof EventDetailsTabs>;

export const Default: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.flow-run.Completed",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc123",
				"prefect.resource.name": "etl-pipeline-run-1",
			},
		}),
	},
};

export const RawTabActive: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.flow-run.Completed",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc123",
				"prefect.resource.name": "etl-pipeline-run-1",
			},
		}),
		defaultTab: "raw",
	},
};

export const WithComplexJsonData: Story = {
	args: {
		event: createFakeEvent({
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
			],
			payload: {
				validated: true,
				duration: 120,
				metadata: {
					source: "api",
					version: "2.0",
					nested: {
						deep: {
							value: "test",
						},
					},
				},
			},
		}),
		defaultTab: "raw",
	},
};
