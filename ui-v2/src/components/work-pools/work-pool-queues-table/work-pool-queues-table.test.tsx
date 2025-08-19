import type { SortingState } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

	const defaultProps = {
		queues: mockQueues,
		searchQuery: "",
		sortState: [{ id: "name", desc: false }] as SortingState,
		totalCount: mockQueues.length,
		workPoolName: "test-pool",
		onSearchChange: vi.fn(),
		onSortingChange: vi.fn(),
	};

	it("renders toolbar and data table", () => {
		render(<WorkPoolQueuesTable {...defaultProps} />);

		// Should render toolbar
		expect(screen.getByTestId("toolbar")).toBeInTheDocument();

		// Should render data table
		expect(screen.getByTestId("data-table")).toBeInTheDocument();
	});

	it("shows correct queue count in toolbar", () => {
		render(<WorkPoolQueuesTable {...defaultProps} />);

		// Should show the total count from mock data
		expect(screen.getByText("3 queues")).toBeInTheDocument();
	});

	it("calls onSearchChange when search input changes", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTable {...defaultProps} onSearchChange={onSearchChange} />,
		);

		// Type in search input
		const searchInput = screen.getByTestId("search-input");
		fireEvent.change(searchInput, { target: { value: "default" } });

		// Should call onSearchChange callback
		expect(onSearchChange).toHaveBeenCalledWith("default");
	});

	it("shows empty state when no queues provided with search query", () => {
		render(
			<WorkPoolQueuesTable
				{...defaultProps}
				queues={[]}
				searchQuery="nonexistent"
			/>,
		);

		// Should show empty state with search query
		expect(screen.getByText("No queues found")).toBeInTheDocument();
	});

	it("shows empty state when no queues and no search query", () => {
		render(<WorkPoolQueuesTable {...defaultProps} queues={[]} />);

		// Should show empty state without search query
		expect(screen.getByText("No queues yet")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<WorkPoolQueuesTable {...defaultProps} className="custom-class" />,
		);

		const tableContainer = container.querySelector(".custom-class");
		expect(tableContainer).toBeInTheDocument();
	});

	it("displays correct counts for different queue data", () => {
		const customPoolQueues = createFakeWorkPoolQueues("custom-pool", 2);
		render(
			<WorkPoolQueuesTable
				{...defaultProps}
				queues={customPoolQueues}
				totalCount={2}
				workPoolName="custom-pool"
			/>,
		);

		expect(screen.getByText("2 queues")).toBeInTheDocument();
	});

	it("passes sorting state to table correctly", () => {
		const customSortState = [{ id: "priority", desc: true }] as SortingState;
		render(
			<WorkPoolQueuesTable {...defaultProps} sortState={customSortState} />,
		);

		// Component should render without errors with custom sort state
		expect(screen.getByTestId("data-table")).toBeInTheDocument();
	});

	it("calls onSortingChange when provided", () => {
		const onSortingChange = vi.fn();
		render(
			<WorkPoolQueuesTable
				{...defaultProps}
				onSortingChange={onSortingChange}
			/>,
		);

		// Component should render without errors
		expect(screen.getByTestId("data-table")).toBeInTheDocument();
	});

	it("shows search query in toolbar input", () => {
		render(<WorkPoolQueuesTable {...defaultProps} searchQuery="test search" />);

		const searchInput = screen.getByTestId("search-input");
		expect(searchInput).toHaveValue("test search");
	});

	it("displays correct results count when filtered", () => {
		const filteredQueues = mockQueues.slice(0, 1); // Only 1 queue
		render(
			<WorkPoolQueuesTable
				{...defaultProps}
				queues={filteredQueues}
				searchQuery="default"
			/>,
		);

		// Should show filtered count
		expect(screen.getByText("1 of 3 queues")).toBeInTheDocument();
	});
});
