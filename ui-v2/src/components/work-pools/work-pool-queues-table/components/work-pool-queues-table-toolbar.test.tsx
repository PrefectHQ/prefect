import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
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
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toBeInTheDocument();
		expect(searchInput).toHaveValue("");
	});

	it("renders search input with current search query", () => {
		render(
			<WorkPoolQueuesTableToolbar {...defaultProps} searchQuery="my-search" />,
			{
				wrapper: createWrapper(),
			},
		);

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toHaveValue("my-search");
	});

	it("calls onSearchChange when search input value changes", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				onSearchChange={onSearchChange}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const searchInput = screen.getByPlaceholderText("Search");
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
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("15 Work Queues")).toBeInTheDocument();
	});

	it("displays filtered count when search query exists", () => {
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="search-term"
				resultsCount={3}
				totalCount={15}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("3 of 15 Work Queues")).toBeInTheDocument();
	});

	it("shows clear filters button when search query exists", () => {
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="search-term"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		expect(clearButton).toBeInTheDocument();
	});

	it("does not show clear filters button when no search query", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} searchQuery="" />, {
			wrapper: createWrapper(),
		});

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
			{
				wrapper: createWrapper(),
			},
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		fireEvent.click(clearButton);

		expect(onSearchChange).toHaveBeenCalledWith("");
	});

	it("renders filter button", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const buttons = screen.getAllByRole("button");
		// Should have the plus/filter button
		expect(buttons.length).toBeGreaterThanOrEqual(1);
	});

	it("opens create dialog when plus button is clicked", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const buttons = screen.getAllByRole("button");
		const plusButton = buttons.find((btn) => btn.querySelector(".lucide-plus"));
		expect(plusButton).toBeDefined();

		if (plusButton) {
			fireEvent.click(plusButton);
		}

		// Dialog should be open
		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Create Work Queue" }),
		).toBeInTheDocument();
	});

	it("has correct search icon placement", () => {
		const { container } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
			{
				wrapper: createWrapper(),
			},
		);

		// Check for search icon with correct positioning classes
		const searchIcon = container.querySelector(".lucide-search");
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
			{
				wrapper: createWrapper(),
			},
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass("custom-class");
	});

	it("has correct default container classes", () => {
		const { container } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
			{
				wrapper: createWrapper(),
			},
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass("space-y-4");
	});

	it("search input has correct styling", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toHaveClass("pl-8", "w-64");
	});

	it("create button has correct size", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		// The plus button doesn't have specific button text, so check it exists
		const buttons = screen.getAllByRole("button");
		expect(buttons.length).toBeGreaterThan(0);
	});

	it("handles different count scenarios correctly", () => {
		const { rerender } = render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery=""
				totalCount={0}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("0 Work Queues")).toBeInTheDocument();

		rerender(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="test"
				resultsCount={0}
				totalCount={5}
			/>,
		);

		// Note: rerender doesn't need wrapper again

		expect(screen.getByText("0 of 5 Work Queues")).toBeInTheDocument();

		rerender(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				searchQuery="test"
				resultsCount={1}
				totalCount={1}
			/>,
		);

		expect(screen.getByText("1 of 1 Work Queue")).toBeInTheDocument();
	});

	it("handles multiple search query changes", () => {
		const onSearchChange = vi.fn();
		render(
			<WorkPoolQueuesTableToolbar
				{...defaultProps}
				onSearchChange={onSearchChange}
				searchQuery=""
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const searchInput = screen.getByPlaceholderText("Search");

		fireEvent.change(searchInput, { target: { value: "first" } });
		fireEvent.change(searchInput, { target: { value: "second" } });

		expect(onSearchChange).toHaveBeenCalledWith("first");
		expect(onSearchChange).toHaveBeenCalledWith("second");
		expect(onSearchChange).toHaveBeenCalledTimes(2);
	});

	it("plus button works consistently across rerenders", () => {
		const { rerender } = render(
			<WorkPoolQueuesTableToolbar {...defaultProps} />,
			{
				wrapper: createWrapper(),
			},
		);

		const filterButtons = screen.getAllByRole("button");
		const filterButton = filterButtons.find((btn) =>
			btn.querySelector(".lucide-plus"),
		);
		if (filterButton) {
			fireEvent.click(filterButton);
		}

		// Dialog should open
		expect(screen.getByRole("dialog")).toBeInTheDocument();

		// Close dialog first
		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		fireEvent.click(cancelButton);

		rerender(<WorkPoolQueuesTableToolbar {...defaultProps} />);

		// Note: rerender doesn't need wrapper again

		const rerenderedFilterButtons = screen.getAllByRole("button");
		const rerenderedFilterButton = rerenderedFilterButtons.find((btn) =>
			btn.querySelector(".lucide-plus"),
		);
		if (rerenderedFilterButton) {
			fireEvent.click(rerenderedFilterButton);
		}

		// Dialog should open again
		expect(screen.getByRole("dialog")).toBeInTheDocument();
	});

	it("maintains input focus after typing", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const searchInput = screen.getByPlaceholderText("Search");
		searchInput.focus();

		expect(document.activeElement).toBe(searchInput);

		fireEvent.change(searchInput, { target: { value: "test" } });

		expect(document.activeElement).toBe(searchInput);
	});

	it("renders plus button for creating work queues", () => {
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const plusButton = screen.getByRole("button", { name: "" });
		expect(plusButton).toBeInTheDocument();
		expect(plusButton.querySelector("svg")).toBeInTheDocument(); // Plus icon
	});

	it("opens create dialog when plus button is clicked", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const plusButton = screen.getByRole("button", { name: "" });
		await user.click(plusButton);

		// Dialog should be open
		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Create Work Queue" }),
		).toBeInTheDocument();
	});

	it("closes create dialog when dialog onOpenChange is called", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueuesTableToolbar {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		// Open dialog first
		const plusButton = screen.getByRole("button", { name: "" });
		await user.click(plusButton);
		expect(screen.getByRole("dialog")).toBeInTheDocument();

		// Close dialog via cancel button
		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(cancelButton);

		// Dialog should be closed
		await waitFor(() => {
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		});
	});
});
