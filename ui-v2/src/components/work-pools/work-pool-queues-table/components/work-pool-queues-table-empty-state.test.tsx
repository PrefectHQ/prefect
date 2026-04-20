import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkPoolQueuesTableEmptyState } from "./work-pool-queues-table-empty-state";

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

		const svgIcon = container.querySelector("svg");
		expect(svgIcon).toBeInTheDocument();
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

	it("renders list icon when hasSearchQuery is false", () => {
		const { container } = render(
			<WorkPoolQueuesTableEmptyState
				hasSearchQuery={false}
				workPoolName="test-pool"
			/>,
		);

		const svgIcon = container.querySelector("svg");
		expect(svgIcon).toBeInTheDocument();
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
