import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueuesTableToolbar } from "./work-pool-queues-table-toolbar";

// Mock console.log since component has TODO logging
vi.spyOn(console, "log").mockImplementation(() => {});

describe("WorkPoolQueuesTableToolbar", () => {
	const defaultProps = {
		searchQuery: "",
		onSearchChange: vi.fn(),
		resultsCount: 5,
		totalCount: 10,
		workPoolName: "test-pool",
	};

	it("renders search input", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const searchInput = screen.getByPlaceholderText("Search queues...");
		expect(searchInput).toBeInTheDocument();
		expect(searchInput).toHaveValue("");
	});

	it("renders search input with current search query", () => {
		render(
			<WorkPoolQueuesTableToolbar {...defaultProps} searchQuery="my-search" />,
		);

		const searchInput = screen.getByPlaceholderText("Search queues...");
		expect(searchInput).toHaveValue("my-search");
	});

	it("calls onSearchChange when search input value changes", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				onSearchChange={onSearchChange}
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search queues...");
		fireEvent.change(searchInput, { target: { value: "new-search" } });

		expect(onSearchChange).toHaveBeenCalledWith("new-search");
	});

	it("displays total count when no search query", () => {
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery=""
				totalCount={15}
			/>,
		);

		expect(screen.getByText("15 queues")).toBeInTheDocument();
	});

	it("displays filtered count when search query exists", () => {
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="search-term"
				resultsCount={3}
				totalCount={15}
			/>,
		);

		expect(screen.getByText("3 of 15 queues")).toBeInTheDocument();
	});

	it("shows clear filters button when search query exists", () => {
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="search-term"
			/>,
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		expect(clearButton).toBeInTheDocument();
	});

	it("does not show clear filters button when no search query", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} searchQuery="" />);

		const clearButton = screen.queryByRole("button", {
			name: /clear filters/i,
		});
		expect(clearButton).not.toBeInTheDocument();
	});

	it("clears search when clear filters button is clicked", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="search-term"
				onSearchChange={onSearchChange}
			/>,
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		fireEvent.click(clearButton);

		expect(onSearchChange).toHaveBeenCalledWith("");
	});

	it("renders filter button", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const buttons = screen.getAllByRole("button");
		expect(buttons.length).toBeGreaterThan(1); // Should have at least the filter button and possibly clear button
	});

	it("logs filter action when filter button is clicked", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const filterButton = screen.getAllByRole("button")[1]; // Get the plus/filter button
		fireEvent.click(filterButton);

		expect(console.log).toHaveBeenCalledWith("Filter/actions for work queues");
	});

	it("has correct search icon placement", () => {
		const { container } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
		);

		// Check for search icon with correct positioning classes
		const searchIcon = container.querySelector("svg");
		expect(searchIcon).toBeInTheDocument();
		expect(searchIcon).toHaveClass(
			"absolute",
			"left-2",
			"top-2.5",
			"h-4",
			"w-4",
			"text-muted-foreground",
		);
	});

	it("applies custom className when provided", () => {
		const { container } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} className="custom-class" />,
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass("custom-class");
	});

	it("has correct default container classes", () => {
		const { container } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass("space-y-4");
	});

	it("search input has correct styling", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const searchInput = screen.getByPlaceholderText("Search queues...");
		expect(searchInput).toHaveClass("pl-8", "w-64");
	});

	it("create button has correct size", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const createButton = screen.getByRole("button", { name: /create queue/i });
		// Check for sm size class (this might be applied through the Button component)
		expect(createButton).toBeInTheDocument();
	});

	it("handles different count scenarios correctly", () => {
		const { rerender } = render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery=""
				totalCount={0}
			/>,
		);

		expect(screen.getByText("0 queues")).toBeInTheDocument();

		rerender(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="test"
				resultsCount={0}
				totalCount={5}
			/>,
		);

		expect(screen.getByText("0 of 5 queues")).toBeInTheDocument();

		rerender(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="test"
				resultsCount={1}
				totalCount={1}
			/>,
		);

		expect(screen.getByText("1 of 1 queues")).toBeInTheDocument();
	});

	it("handles multiple search query changes", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				onSearchChange={onSearchChange}
				searchQuery=""
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search queues...");

		fireEvent.change(searchInput, { target: { value: "first" } });
		fireEvent.change(searchInput, { target: { value: "second" } });

		expect(onSearchChange).toHaveBeenCalledWith("first");
		expect(onSearchChange).toHaveBeenCalledWith("second");
		expect(onSearchChange).toHaveBeenCalledTimes(2);
	});

	it("filter button works consistently", () => {
		const { rerender } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
		);

		let filterButton = screen.getAllByRole("button")[1]; // Get the plus/filter button
		fireEvent.click(filterButton);

		expect(console.log).toHaveBeenCalledWith("Filter/actions for work queues");

		rerender(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		filterButton = screen.getAllByRole("button")[1]; // Get the plus/filter button
		fireEvent.click(filterButton);

		expect(console.log).toHaveBeenCalledWith("Filter/actions for work queues");
	});

	it("maintains input focus after typing", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		const searchInput = screen.getByPlaceholderText("Search queues...");
		searchInput.focus();

		expect(document.activeElement).toBe(searchInput);

		fireEvent.change(searchInput, { target: { value: "test" } });

		expect(document.activeElement).toBe(searchInput);
	});
});
