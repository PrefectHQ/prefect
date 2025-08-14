import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import type { WorkPool } from "@/api/work-pools";
import { reactQueryDecorator } from "@/storybook/utils";
import { WorkPoolToggle } from "./work-pool-toggle";

const mockWorkPool: WorkPool = {
	id: "wp-123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "my-work-pool",
	description: "Test work pool",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: null,
	status: "READY",
};

const mockWorkPoolPaused: WorkPool = {
	...mockWorkPool,
	status: "PAUSED",
	is_paused: true,
};

const meta: Meta<typeof WorkPoolToggle> = {
	title: "Components/WorkPools/WorkPoolToggle",
	component: WorkPoolToggle,
	decorators: [reactQueryDecorator],
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.patch(buildApiUrl("/work_pools/:name"), async ({ request }) => {
					const body = await request.json();
					const requestBody = body as { is_paused: boolean };
					return HttpResponse.json({
						...mockWorkPool,
						is_paused: requestBody.is_paused,
						status: requestBody.is_paused ? "PAUSED" : "READY",
					});
				}),
			],
		},
	},
	args: {
		onUpdate: fn(),
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolToggle>;

export const Active: Story = {
	args: {
		workPool: mockWorkPool,
	},
};

export const Paused: Story = {
	args: {
		workPool: mockWorkPoolPaused,
	},
};

export const Loading: Story = {
	args: {
		workPool: mockWorkPool,
	},
	parameters: {
		msw: {
			handlers: [
				http.patch(buildApiUrl("/work_pools/:name"), async () => {
					// Simulate a slow response
					await new Promise((resolve) => setTimeout(resolve, 5000));
					return HttpResponse.json({});
				}),
			],
		},
	},
};

export const WithError: Story = {
	args: {
		workPool: mockWorkPool,
	},
	parameters: {
		msw: {
			handlers: [
				http.patch(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json(
						{ detail: "Failed to update work pool" },
						{ status: 500 },
					);
				}),
			],
		},
	},
};
