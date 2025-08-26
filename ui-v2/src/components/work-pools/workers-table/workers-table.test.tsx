import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { createFakeWorkPoolWorkers } from "@/mocks/create-fake-work-pool-worker";
import { WorkersTable } from "./workers-table";

const mockWorkers = createFakeWorkPoolWorkers(3, {
	work_pool_id: "test-pool-id",
});

const mockWorkersOnline = [
	...mockWorkers,
	{
		...mockWorkers[0],
		name: "online-worker",
		status: "ONLINE" as const,
	},
];

// Test wrapper that provides state management for the controlled component
const WorkersTableWrapper = ({
	workPoolName,
	workers,
}: {
	workPoolName: string;
	workers: typeof mockWorkersOnline;
}) => {
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

	return (
		<WorkersTable
			workPoolName={workPoolName}
			workers={workers}
			pagination={pagination}
			columnFilters={columnFilters}
			onPaginationChange={setPagination}
			onColumnFiltersChange={setColumnFilters}
		/>
	);
};

const renderWithQueryClient = (component: React.ReactElement) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});

	return render(
		<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
	);
};

describe("WorkersTable", () => {
	it("renders workers list correctly", () => {
		renderWithQueryClient(
			<WorkersTableWrapper
				workPoolName="test-pool"
				workers={mockWorkersOnline}
			/>,
		);

		expect(screen.getByText("online-worker")).toBeInTheDocument();
		expect(screen.getByText("4 workers")).toBeInTheDocument();
	});

	it("filters workers based on search query", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkersTableWrapper
				workPoolName="test-pool"
				workers={mockWorkersOnline}
			/>,
		);

		expect(screen.getByText("online-worker")).toBeInTheDocument();

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "online");

		await waitFor(() => {
			expect(screen.getByText("1 of 4 workers")).toBeInTheDocument();
		});

		expect(screen.getByText("online-worker")).toBeInTheDocument();
		expect(screen.queryByText(mockWorkers[0].name)).not.toBeInTheDocument();
	});

	it("shows empty state when no workers", () => {
		renderWithQueryClient(
			<WorkersTableWrapper workPoolName="empty-pool" workers={[]} />,
		);

		expect(screen.getByText("No workers running")).toBeInTheDocument();
		expect(screen.getByText("0 workers")).toBeInTheDocument();
		expect(
			screen.getByText('prefect worker start --pool "empty-pool"'),
		).toBeInTheDocument();
	});

	it("shows 'no results' when search has no matches", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkersTableWrapper
				workPoolName="test-pool"
				workers={mockWorkersOnline}
			/>,
		);

		expect(screen.getByText("4 workers")).toBeInTheDocument();

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "nonexistent-worker");

		await waitFor(() => {
			expect(screen.getByText("No workers found")).toBeInTheDocument();
		});

		expect(
			screen.getByText("No workers match your search criteria."),
		).toBeInTheDocument();
		expect(screen.getByText("0 of 4 workers")).toBeInTheDocument();
	});

	it("clears search filters", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkersTableWrapper
				workPoolName="test-pool"
				workers={mockWorkersOnline}
			/>,
		);

		expect(screen.getByText("4 workers")).toBeInTheDocument();

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "online");

		await waitFor(() => {
			expect(screen.getByText("1 of 4 workers")).toBeInTheDocument();
		});

		const clearButton = screen.getByText("Clear filters");
		await user.click(clearButton);

		await waitFor(() => {
			expect(screen.getByText("4 workers")).toBeInTheDocument();
		});

		expect(searchInput).toHaveValue("");
	});
});
