import type { Meta, StoryObj } from "@storybook/react";
import type { SortingState } from "@tanstack/react-table";
import { fn } from "storybook/test";
import { createFakeWorkPoolQueues } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { WorkPoolQueuesTable } from "./work-pool-queues-table";

const mockQueues = createFakeWorkPoolQueues("test-pool", 5);

const mockQueuesWithVariedStatuses = createFakeWorkPoolQueues("test-pool", 6, [
	{}, // default queue
	{ name: "high-priority", priority: 0, status: "READY" },
	{ name: "paused-queue", status: "PAUSED" },
	{ name: "not-ready-queue", status: "NOT_READY" },
	{ name: "limited-queue", concurrency_limit: 10 },
]);

const meta = {
	title: "Components/WorkPools/WorkPoolQueuesTable",
	component: WorkPoolQueuesTable,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	parameters: {
		layout: "padded",
	},
	args: {
		onSearchChange: fn(),
		onSortingChange: fn(),
	},
	argTypes: {
		searchQuery: {
			control: "text",
			description: "Current search query value",
		},
		sortState: {
			control: "object",
			description: "Current sorting state from TanStack Table",
		},
		totalCount: {
			control: "number",
			description: "Total number of queues (used for display when filtering)",
		},
		workPoolName: {
			control: "text",
			description: "Name of the work pool",
		},
		className: {
			control: "text",
			description: "Additional CSS classes to apply",
		},
		onSearchChange: {
			description: "Callback fired when search query changes",
		},
		onSortingChange: {
			description: "Callback fired when sorting state changes",
		},
	},
	tags: ["autodocs"],
} satisfies Meta<typeof WorkPoolQueuesTable>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		queues: mockQueues,
		searchQuery: "",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: mockQueues.length,
		workPoolName: "test-pool",
	},
};

export const WithVariedStatuses: Story = {
	args: {
		queues: mockQueuesWithVariedStatuses,
		searchQuery: "",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: mockQueuesWithVariedStatuses.length,
		workPoolName: "varied-pool",
	},
	parameters: {
		docs: {
			description: {
				story:
					"Shows queues with different statuses, priorities, and concurrency limits.",
			},
		},
	},
};

export const EmptyState: Story = {
	args: {
		queues: [],
		searchQuery: "",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: 0,
		workPoolName: "empty-pool",
	},
	parameters: {
		docs: {
			description: {
				story: "Shows the empty state when no queues exist for the work pool.",
			},
		},
	},
};

export const WithSearchQuery: Story = {
	args: {
		queues: mockQueues.filter((q) => q.name.includes("default")), // Filtered results
		searchQuery: "default",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: mockQueues.length, // Total before filtering
		workPoolName: "test-pool",
	},
	parameters: {
		docs: {
			description: {
				story:
					"Shows the table with a search query applied and filtered results.",
			},
		},
	},
};

export const NoResultsFromSearch: Story = {
	args: {
		queues: [], // No results after filtering
		searchQuery: "nonexistent",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: mockQueues.length, // Total before filtering
		workPoolName: "test-pool",
	},
	parameters: {
		docs: {
			description: {
				story: "Shows the empty state when search query yields no results.",
			},
		},
	},
};

export const SortedByPriority: Story = {
	args: {
		queues: mockQueuesWithVariedStatuses.sort(
			(a, b) => (a.priority || 0) - (b.priority || 0),
		),
		searchQuery: "",
		sortState: [{ id: "priority", desc: false }] as SortingState,
		totalCount: mockQueuesWithVariedStatuses.length,
		workPoolName: "test-pool",
	},
	parameters: {
		docs: {
			description: {
				story: "Shows the table sorted by priority column.",
			},
		},
	},
};
