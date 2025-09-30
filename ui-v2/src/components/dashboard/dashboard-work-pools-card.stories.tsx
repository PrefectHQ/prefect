import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeWorkPool } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { DashboardWorkPoolsCard } from "./dashboard-work-pools-card";

const meta = {
	title: "Components/Dashboard/DashboardWorkPoolsCard",
	component: DashboardWorkPoolsCard,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof DashboardWorkPoolsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						createFakeWorkPool({
							name: "Production Pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "Staging Pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "Development Pool",
							is_paused: false,
							status: "NOT_READY",
						}),
					]);
				}),
			],
		},
	},
};

export const SingleWorkPool: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						createFakeWorkPool({
							name: "Production Pool",
							is_paused: false,
							status: "READY",
						}),
					]);
				}),
			],
		},
	},
};

export const EmptyState: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						createFakeWorkPool({
							name: "Paused Pool",
							is_paused: true,
						}),
					]);
				}),
			],
		},
	},
};

export const MixedStatuses: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						createFakeWorkPool({
							name: "Ready Pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "Not Ready Pool",
							is_paused: false,
							status: "NOT_READY",
						}),
						createFakeWorkPool({
							name: "Unknown Status Pool",
							is_paused: false,
							status: null,
						}),
					]);
				}),
			],
		},
	},
};

export const NoWorkPools: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};
