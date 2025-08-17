import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import type { WorkPool } from "@/api/work-pools";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolMenu } from "./work-pool-menu";

const mockWorkPool: WorkPool = {
	id: "wp-123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "my-work-pool",
	description: "Test work pool for menu stories",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: null,
	status: "READY",
};

const meta: Meta<typeof WorkPoolMenu> = {
	title: "Components/WorkPools/WorkPoolMenu",
	component: WorkPoolMenu,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.delete(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json({});
				}),
			],
		},
	},
	args: {
		onUpdate: fn(),
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolMenu>;

export const Default: Story = {
	args: {
		workPool: mockWorkPool,
	},
};

// TODO: Add permission stories when WorkPool type supports `can` field

export const LongWorkPoolName: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			name: "very-long-work-pool-name-that-might-affect-menu-positioning",
		},
	},
};

export const WithDeleteError: Story = {
	args: {
		workPool: mockWorkPool,
	},
	parameters: {
		msw: {
			handlers: [
				http.delete(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json(
						{ detail: "Cannot delete work pool with active workers" },
						{ status: 400 },
					);
				}),
			],
		},
	},
};
