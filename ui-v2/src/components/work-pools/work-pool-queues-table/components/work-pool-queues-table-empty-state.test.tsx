import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueuesTableEmptyState } from "./work-pool-queues-table-empty-state";

// Mock console.log since component has TODO logging
vi.spyOn(console, "log").mockImplementation(() => {});

describe("WorkPoolQueuesTableEmptyState", () => {
	it("renders search empty state when hasSearchQuery is true", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={true}
				workPoolName="test-pool"
			/>,
		);

		expect(screen.getByText("No queues found")).toBeInTheDocument();
		expect(
			screen.getByText(
				"No queues match your search criteria. Try adjusting your search.",
			),
		).toBeInTheDocument();
	});

	it("renders search empty state with search icon when hasSearchQuery is true", () => {
		const { container } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={true}
				workPoolName="test-pool"
			/>,
		);

		// Check for search icon (should have lucide-react search icon classes)
		const searchIcon = container.querySelector("svg");
		expect(searchIcon).toBeInTheDocument();
		expect(searchIcon).toHaveClass(
			"h-12",
			"w-12",
			"text-muted-foreground",
			"mb-4",
		);
	});

	it("renders no queues empty state when hasSearchQuery is false", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		expect(screen.getByText("No queues yet")).toBeInTheDocument();
		expect(
			screen.getByText(
				"This work pool doesn't have any queues yet. Create your first queue to start organizing work.",
			),
		).toBeInTheDocument();
	});

	it("renders create queue button when hasSearchQuery is false", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		const createButton = screen.getByRole("button", { name: /create queue/i });
		expect(createButton).toBeInTheDocument();
	});

	it("does not render create queue button when hasSearchQuery is true", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={true}
				workPoolName="test-pool"
			/>,
		);

		const createButton = screen.queryByRole("button", {
			name: /create queue/i,
		});
		expect(createButton).not.toBeInTheDocument();
	});

	it("logs work pool name when create queue button is clicked", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="my-work-pool"
			/>,
		);

		const createButton = screen.getByRole("button", { name: /create queue/i });
		fireEvent.click(createButton);

		expect(console.log).toHaveBeenCalledWith(
			"Create queue for pool:",
			"my-work-pool",
		);
	});

	it("renders plus icon in button and container for no queues state", () => {
		const { container } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		// Check for plus icon in the circular background
		const circularContainer = container.querySelector(
			".h-12.w-12.rounded-full.bg-muted",
		);
		expect(circularContainer).toBeInTheDocument();

		// Check for plus icon in the button
		const createButton = screen.getByRole("button", { name: /create queue/i });
		expect(createButton).toBeInTheDocument();
	});

	it("uses correct work pool name in different scenarios", () => {
		// Test with different work pool names
		const { rerender } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="production-pool"
			/>,
		);

		let createButton = screen.getByRole("button", { name: /create queue/i });
		fireEvent.click(createButton);

		expect(console.log).toHaveBeenCalledWith(
			"Create queue for pool:",
			"production-pool",
		);

		// Test with a different work pool name
		rerender(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="development-pool"
			/>,
		);

		createButton = screen.getByRole("button", { name: /create queue/i });
		fireEvent.click(createButton);

		expect(console.log).toHaveBeenCalledWith(
			"Create queue for pool:",
			"development-pool",
		);
	});

	it("has correct container structure and styling", () => {
		const { container } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass(
			"flex",
			"flex-col",
			"items-center",
			"justify-center",
			"py-12",
			"text-center",
		);
	});

	it("search empty state has correct structure and styling", () => {
		const { container } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={true}
				workPoolName="test-pool"
			/>,
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass(
			"flex",
			"flex-col",
			"items-center",
			"justify-center",
			"py-12",
			"text-center",
		);
	});

	it("displays correct text content for search state", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={true}
				workPoolName="test-pool"
			/>,
		);

		expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
			"No queues found",
		);
		expect(
			screen.getByText(/no queues match your search criteria/i),
		).toBeInTheDocument();
	});

	it("displays correct text content for no queues state", () => {
		render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
			"No queues yet",
		);
		expect(
			screen.getByText(/this work pool doesn't have any queues yet/i),
		).toBeInTheDocument();
	});
});
