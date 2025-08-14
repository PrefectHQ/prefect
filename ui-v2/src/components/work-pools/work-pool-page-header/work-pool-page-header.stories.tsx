import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import type { WorkPool } from "@/api/work-pools";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolPageHeader } from "./work-pool-page-header";

const mockWorkPool: WorkPool = {
	id: "wp-123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "my-work-pool",
	description: "Test work pool for stories",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: 10,
	status: "READY",
};

const mockWorkPoolPaused: WorkPool = {
	...mockWorkPool,
	status: "PAUSED",
	is_paused: true,
};

const mockWorkPoolNotReady: WorkPool = {
	...mockWorkPool,
	status: "NOT_READY",
};

const meta: Meta<typeof WorkPoolPageHeader> = {
	title: "Components/WorkPools/WorkPoolPageHeader",
	component: WorkPoolPageHeader,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
		msw: {
			handlers: [
				http.patch(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json({});
				}),
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
type Story = StoryObj<typeof WorkPoolPageHeader>;

export const Default: Story = {
	args: {
		workPool: mockWorkPool,
	},
};

export const Paused: Story = {
	args: {
		workPool: mockWorkPoolPaused,
	},
};

export const NotReady: Story = {
	args: {
		workPool: mockWorkPoolNotReady,
	},
};

export const LongName: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			name: "very-long-work-pool-name-that-might-wrap-or-truncate",
		},
	},
};

export const WithDescription: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			description:
				"This is a longer description that provides more context about what this work pool is used for in the system",
		},
	},
};

export const WithConcurrencyLimit: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			concurrency_limit: 100,
		},
	},
};

// TODO: Add permission stories when WorkPool type supports `can` field
// export const NoPermissions: Story = {
// 	args: {
// 		workPool: {
// 			...mockWorkPool,
// 			can: {
// 				read: true,
// 				update: false,
// 				delete: false,
// 			},
// 		},
// 	},
// };

// export const AllPermissions: Story = {
// 	args: {
// 		workPool: {
// 			...mockWorkPool,
// 			can: {
// 				read: true,
// 				update: true,
// 				delete: true,
// 			},
// 		},
// 	},
// };
