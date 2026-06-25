import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueuesTableToolbar } from "./work-pool-queues-table-toolbar";

// Mock console.log since component has TODO logging
vi.spyOn(console, "log").mockImplementation(() => {});

type ToolbarProps = React.ComponentProps<typeof WorkPoolQueuesTableToolbar>;

const ToolbarRouter = (props: ToolbarProps) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolQueuesTableToolbar {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return <RouterProvider router={router} />;
};

describe("WorkPoolQueuesTableToolbar", () => {
	const defaultProps: ToolbarProps = {
		searchQuery: "",
		onSearchChange: vi.fn(),
		resultsCount: 5,
		totalCount: 10,
		workPoolName: "test-pool",
	};

	it("renders search input", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toBeInTheDocument();
		expect(searchInput).toHaveValue("");
	});

	it("renders search input with current search query", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} searchQuery="my-search" />, {
				wrapper: createWrapper(),
			}),
		);

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toHaveValue("my-search");
	});

	it("calls onSearchChange when search input value changes", async () => {
		const onSearchChange = vi.fn();
		await waitFor(() =>
			render(
				<ToolbarRouter {...defaultProps} onSearchChange={onSearchChange} />,
				{ wrapper: createWrapper() },
			),
		);

		const searchInput = screen.getByPlaceholderText("Search");
		fireEvent.change(searchInput, { target: { value: "new-search" } });

		expect(onSearchChange).toHaveBeenCalledWith("new-search");
	});

	it("displays total count when no search query", async () => {
		await waitFor(() =>
			render(
				<ToolbarRouter {...defaultProps} searchQuery="" totalCount={15} />,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("15 Work Queues")).toBeInTheDocument();
	});

	it("displays filtered count when search query exists", async () => {
		await waitFor(() =>
			render(
				<ToolbarRouter
					{...defaultProps}
					searchQuery="search-term"
					resultsCount={3}
					totalCount={15}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("3 of 15 Work Queues")).toBeInTheDocument();
	});

	it("shows clear filters button when search query exists", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} searchQuery="search-term" />, {
				wrapper: createWrapper(),
			}),
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		expect(clearButton).toBeInTheDocument();
	});

	it("does not show clear filters button when no search query", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} searchQuery="" />, {
				wrapper: createWrapper(),
			}),
		);

		const clearButton = screen.queryByRole("button", {
			name: /clear filters/i,
		});
		expect(clearButton).not.toBeInTheDocument();
	});

	it("clears search when clear filters button is clicked", async () => {
		const onSearchChange = vi.fn();
		await waitFor(() =>
			render(
				<ToolbarRouter
					{...defaultProps}
					searchQuery="search-term"
					onSearchChange={onSearchChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		const clearButton = screen.getByRole("button", { name: /clear filters/i });
		fireEvent.click(clearButton);

		expect(onSearchChange).toHaveBeenCalledWith("");
	});

	it("renders plus button as a link to the create page", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		const plusLink = screen.getByRole("link");
		expect(plusLink).toBeInTheDocument();
		expect(plusLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/test-pool/queue/create",
		);
	});

	it("has correct search icon placement", async () => {
		const { container } = await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
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

	it("applies custom className when provided", async () => {
		const { container } = await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} className="custom-class" />, {
				wrapper: createWrapper(),
			}),
		);

		const wrapper = container.querySelector(".custom-class");
		expect(wrapper).toBeInTheDocument();
	});

	it("has correct default container classes", async () => {
		const { container } = await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		const wrapper = container.querySelector(".space-y-4");
		expect(wrapper).toBeInTheDocument();
	});

	it("search input has correct styling", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		const searchInput = screen.getByPlaceholderText("Search");
		expect(searchInput).toHaveClass("pl-8", "w-64");
	});

	it("handles zero total count", async () => {
		await waitFor(() =>
			render(
				<ToolbarRouter {...defaultProps} searchQuery="" totalCount={0} />,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("0 Work Queues")).toBeInTheDocument();
	});

	it("handles filtered results showing zero matches", async () => {
		await waitFor(() =>
			render(
				<ToolbarRouter
					{...defaultProps}
					searchQuery="test"
					resultsCount={0}
					totalCount={5}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("0 of 5 Work Queues")).toBeInTheDocument();
	});

	it("handles singular Work Queue label", async () => {
		await waitFor(() =>
			render(
				<ToolbarRouter
					{...defaultProps}
					searchQuery="test"
					resultsCount={1}
					totalCount={1}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("1 of 1 Work Queue")).toBeInTheDocument();
	});

	it("handles multiple search query changes", async () => {
		const onSearchChange = vi.fn();
		await waitFor(() =>
			render(
				<ToolbarRouter
					{...defaultProps}
					onSearchChange={onSearchChange}
					searchQuery=""
				/>,
				{ wrapper: createWrapper() },
			),
		);

		const searchInput = screen.getByPlaceholderText("Search");

		fireEvent.change(searchInput, { target: { value: "first" } });
		fireEvent.change(searchInput, { target: { value: "second" } });

		expect(onSearchChange).toHaveBeenCalledWith("first");
		expect(onSearchChange).toHaveBeenCalledWith("second");
		expect(onSearchChange).toHaveBeenCalledTimes(2);
	});

	it("maintains input focus after typing", async () => {
		await waitFor(() =>
			render(<ToolbarRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		const searchInput = screen.getByPlaceholderText("Search");
		searchInput.focus();

		expect(document.activeElement).toBe(searchInput);

		fireEvent.change(searchInput, { target: { value: "test" } });

		expect(document.activeElement).toBe(searchInput);
	});
});
