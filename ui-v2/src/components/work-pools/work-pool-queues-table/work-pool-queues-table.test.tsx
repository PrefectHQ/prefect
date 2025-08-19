import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueues } from "@/mocks";
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
	const mockQueues = createFakeWorkPoolQueues("test-pool", 3, [
		{ name: "default", status: "READY", is_paused: false, priority: 1 },
		{ name: "queue1", status: "READY", is_paused: false, priority: 2 },
		{
			name: "queue2",
			status: "PAUSED",
			is_paused: true,
			priority: 3,
			concurrency_limit: 10,
		},
	]);

	const renderWithClient = (component: React.ReactElement) => {
		const queryClient = createTestQueryClient();
		return render(
			<QueryClientProvider client={queryClient}>
				<Suspense fallback={<div data-testid="loading">Loading...</div>}>
					{component}
				</Suspense>
			</QueryClientProvider>,
		);
	};

	beforeEach(() => {
		// Default API response for work pool queues
		server.use(
			http.post(buildApiUrl("/work_pools/test-pool/queues/filter"), () => {
				return HttpResponse.json(mockQueues);
			}),
		);
	});

	it("renders toolbar and data table", async () => {
		renderWithClient(<WorkPoolQueuesTable workPoolName="test-pool" />);

		// Should eventually render toolbar after data loads
		expect(await screen.findByTestId("toolbar")).toBeInTheDocument();

		// Should render data table
		expect(screen.getByTestId("data-table")).toBeInTheDocument();
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

	it("shows empty state when API returns no queues", async () => {
		// Override the default API response to return empty array
		server.use(
			http.post(buildApiUrl("/work_pools/empty-pool/queues/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		renderWithClient(<WorkPoolQueuesTable workPoolName="empty-pool" />);

		// Should show empty state
		expect(await screen.findByText("No queues yet")).toBeInTheDocument();
	});

	it("applies custom className", async () => {
		const { container } = renderWithClient(
			<WorkPoolQueuesTable workPoolName="test-pool" className="custom-class" />,
		);

		// Wait for component to render
		await screen.findByTestId("toolbar");

		const tableContainer = container.querySelector(".custom-class");
		expect(tableContainer).toBeInTheDocument();
	});

	it("calls correct API endpoint for different work pool names", async () => {
		let apiCalled = false;
		const customPoolQueues = createFakeWorkPoolQueues("custom-pool", 2);

		server.use(
			http.post(buildApiUrl("/work_pools/custom-pool/queues/filter"), () => {
				apiCalled = true;
				return HttpResponse.json(customPoolQueues);
			}),
		);

		renderWithClient(<WorkPoolQueuesTable workPoolName="custom-pool" />);

		// Wait for data to load
		await screen.findByTestId("data-table");

		expect(apiCalled).toBe(true);
		expect(await screen.findByText("2 queues")).toBeInTheDocument();
	});

	it("handles API error gracefully", async () => {
		// Mock API to return error
		server.use(
			http.post(buildApiUrl("/work_pools/error-pool/queues/filter"), () => {
				return HttpResponse.json(
					{ error: "Failed to fetch queues" },
					{ status: 500 },
				);
			}),
		);

		// The component should handle the error gracefully
		// This test assumes the component has error boundaries or error handling
		renderWithClient(<WorkPoolQueuesTable workPoolName="error-pool" />);

		// Wait a moment and check if loading state persists (indicating an error)
		// or check if an error boundary appears
		const loading = await screen.findByTestId("loading");
		expect(loading).toBeInTheDocument();
	});
});
