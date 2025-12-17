import type { Meta, StoryObj } from "@storybook/react";
import { createFakeEvent } from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { EventDetailsHeader } from "./event-details-header";

const meta = {
	title: "Components/Events/EventDetailsHeader",
	component: EventDetailsHeader,
	decorators: [routerDecorator],
} satisfies Meta<typeof EventDetailsHeader>;

export default meta;
type Story = StoryObj<typeof EventDetailsHeader>;

export const Default: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.flow-run.Completed",
		}),
	},
};

export const FlowRunFailed: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.flow-run.Failed",
		}),
	},
};

export const TaskRunRunning: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.task-run.Running",
		}),
	},
};

export const DeploymentCreated: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect.deployment.Created",
		}),
	},
};

export const LongEventName: Story = {
	args: {
		event: createFakeEvent({
			event:
				"prefect.flow-run.very-long-state-name-that-might-cause-wrapping-issues.Completed",
		}),
	},
};

export const PrefectCloudEvent: Story = {
	args: {
		event: createFakeEvent({
			event: "prefect-cloud.automation.triggered",
		}),
	},
};
