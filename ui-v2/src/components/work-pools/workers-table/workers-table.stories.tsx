import type { Meta, StoryObj } from "@storybook/react";
import { useSuspenseQuery } from "@tanstack/react-query";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { buildListWorkPoolWorkersQuery } from "@/api/work-pools";
import { createFakeWorkPoolWorkers } from "@/mocks/create-fake-work-pool-worker";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { toastDecorator } from "@/storybook/utils/toast-decorator";
import { useWorkersTableState } from "./hooks/use-workers-table-state";
import { WorkersTable } from "./workers-table";

const mockWorkers = createFakeWorkPoolWorkers(5, {
	work_pool_id: "test-pool-id",
});

const mockWorkersWithVariety = [
	...mockWorkers.slice(0, 2),
	{
		...mockWorkers[2],
		name: "online-worker",
		status: "ONLINE" as const,
		last_heartbeat_time: new Date().toISOString(),
	},
	{
		...mockWorkers[3],
		name: "offline-worker",
		status: "OFFLINE" as const,
		last_heartbeat_time: new Date(
			Date.now() - 24 * 60 * 60 * 1000,
		).toISOString(),
	},
	{
		...mockWorkers[4],
		name: "recent-worker",
		status: "ONLINE" as const,
		last_heartbeat_time: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
	},
];

// Wrapper component that handles state management for Storybook
const WorkersTableStory = ({ workPoolName }: { workPoolName: string }) => {
	const { data: workers = [] } = useSuspenseQuery(
		buildListWorkPoolWorkersQuery(workPoolName),
	);
	const {
		pagination,
		columnFilters,
		onPaginationChange,
		onColumnFiltersChange,
	} = useWorkersTableState();

	return (
		<WorkersTable
			workPoolName={workPoolName}
			workers={workers}
			pagination={pagination}
			columnFilters={columnFilters}
			onPaginationChange={onPaginationChange}
			onColumnFiltersChange={onColumnFiltersChange}
		/>
	);
};

const meta = {
	title: "Components/WorkPools/WorkersTable",
	component: WorkersTableStory,
	decorators: [toastDecorator, reactQueryDecorator],
	parameters: {
		layout: "padded",
	},
	args: {
		workPoolName: "test-pool",
	},
} satisfies Meta<typeof WorkersTableStory>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/:name/workers/filter"), (req) => {
					if (req.params.name === "test-pool") {
						return HttpResponse.json(mockWorkersWithVariety);
					}
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const EmptyState: Story = {
	args: {
		workPoolName: "empty-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/:name/workers/filter"), (req) => {
					if (req.params.name === "empty-pool") {
						return HttpResponse.json([]);
					}
					return HttpResponse.json(mockWorkersWithVariety);
				}),
			],
		},
	},
};

export const Loading: Story = {
	args: {
		workPoolName: "loading-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/:name/workers/filter"), (req) => {
					if (req.params.name === "loading-pool") {
						return new Promise(() => {}); // Never resolves
					}
					return HttpResponse.json(mockWorkersWithVariety);
				}),
			],
		},
	},
};

export const SingleWorker: Story = {
	args: {
		workPoolName: "single-worker-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/:name/workers/filter"), (req) => {
					if (req.params.name === "single-worker-pool") {
						return HttpResponse.json([mockWorkersWithVariety[0]]);
					}
					return HttpResponse.json(mockWorkersWithVariety);
				}),
			],
		},
	},
};

export const ManyWorkers: Story = {
	args: {
		workPoolName: "many-workers-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/:name/workers/filter"), (req) => {
					if (req.params.name === "many-workers-pool") {
						const manyWorkers = createFakeWorkPoolWorkers(50, {
							work_pool_id: "many-workers-pool-id",
						});
						return HttpResponse.json(manyWorkers);
					}
					return HttpResponse.json(mockWorkersWithVariety);
				}),
			],
		},
	},
};
