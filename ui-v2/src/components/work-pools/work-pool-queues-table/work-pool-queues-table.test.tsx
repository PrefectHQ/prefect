import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueuesTable } from "./work-pool-queues-table";

// Mock the child components
vi.mock("./components/work-pool-queues-table-toolbar", () => ({
	WorkPoolQueuesTableToolbar: vi.fn(
		(props: {
			searchQuery: string;
			onSearchChange: (query: string) => void;
			resultsCount: number;
			totalCount: number;
		}) => (
			<div data-testid="toolbar">
				<input
					data-testid="search-input"
					value={props.searchQuery}
					onChange={(e) => props.onSearchChange(e.target.value)}
					placeholder="Search queues..."
				/>
				<span data-testid="results-count">
					{props.searchQuery
						? `${props.resultsCount} of ${props.totalCount} queues`
						: `${props.totalCount} queues`}
				</span>
			</div>
		),
	),
}));

vi.mock("./components/work-pool-queues-table-empty-state", () => ({
	WorkPoolQueuesTableEmptyState: vi.fn(({ hasSearchQuery }) => (
		<div data-testid="empty-state">
			{hasSearchQuery ? "No queues found" : "No queues yet"}
		</div>
	)),
}));

vi.mock("@/components/ui/data-table", () => ({
	DataTable: vi.fn(
		(props: { table: { getRowModel: () => { rows: unknown[] } } }) => (
			<div data-testid="data-table">
				<div data-testid="table-rows">
					{props.table.getRowModel().rows.length} rows
				</div>
			</div>
		),
	),
}));

// Mock the API call by mocking the useSuspenseQuery hook
vi.mock("@tanstack/react-query", async () => {
	const actual = await vi.importActual("@tanstack/react-query");
	return {
		...actual,
		useSuspenseQuery: vi.fn(() => ({
			data: [
				{ name: "default", id: "1" },
				{ name: "queue1", id: "2" },
				{ name: "queue2", id: "3" },
			],
		})),
	};
});

const createTestQueryClient = () => {
	return new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
};

describe("WorkPoolQueuesTable", () => {
	const renderWithClient = (component: React.ReactElement) => {
		const queryClient = createTestQueryClient();
		return render(
			<QueryClientProvider client={queryClient}>
				{component}
			</QueryClientProvider>,
		);
	};

	it("renders toolbar and data table", async () => {
		renderWithClient(<WorkPoolQueuesTable workPoolName="test-pool" />);

		// Should render toolbar
		expect(screen.getByTestId("toolbar")).toBeInTheDocument();

		// Should eventually render data table after data loads
		expect(await screen.findByTestId("data-table")).toBeInTheDocument();
	});

	it("shows correct queue count in toolbar", async () => {
		renderWithClient(<WorkPoolQueuesTable workPoolName="test-pool" />);

		// Should show the total count from mock data
		expect(await screen.findByText("3 queues")).toBeInTheDocument();
	});

	it("filters queues based on search query", async () => {
		renderWithClient(<WorkPoolQueuesTable workPoolName="test-pool" />);

		// Wait for initial load
		await screen.findByTestId("data-table");

		// Type in search input
		const searchInput = screen.getByTestId("search-input");
		fireEvent.change(searchInput, { target: { value: "default" } });

		// Should show filtered results
		expect(await screen.findByText(/1 of 3 queues/)).toBeInTheDocument();
	});

	it("shows empty state when no queues match search", async () => {
		renderWithClient(<WorkPoolQueuesTable workPoolName="test-pool" />);

		// Wait for initial load
		await screen.findByTestId("data-table");

		// Search for something that won't match
		const searchInput = screen.getByTestId("search-input");
		fireEvent.change(searchInput, { target: { value: "nonexistent" } });

		// Should show empty state
		expect(await screen.findByText("No queues found")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = renderWithClient(
			<WorkPoolQueuesTable workPoolName="test-pool" className="custom-class" />,
		);

		const tableContainer = container.querySelector(".custom-class");
		expect(tableContainer).toBeInTheDocument();
	});
});
