import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { subYears } from "date-fns";
import { describe, expect, it } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueDetails } from "./work-pool-queue-details";

// Create a date that's exactly 1.5 years ago to ensure it formats as "over 1 year ago"
const overOneYearAgo = subYears(new Date(), 1.5).toISOString();

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolQueueDetails", () => {
	it("renders basic work pool queue information", () => {
		const mockQueue = createFakeWorkPoolQueue({
			id: "test-queue-id",
			name: "test-queue",
			description: "A test work pool queue",
			priority: 5,
			concurrency_limit: 10,
			status: "READY",
			created: overOneYearAgo,
			updated: overOneYearAgo,
			last_polled: overOneYearAgo,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		// Check work pool name
		expect(screen.getByText("test-work-pool")).toBeInTheDocument();

		// Check description
		expect(screen.getByText("A test work pool queue")).toBeInTheDocument();

		// Check priority
		expect(screen.getByText("5")).toBeInTheDocument();

		// Check concurrency limit
		expect(screen.getByText("10")).toBeInTheDocument();

		// Check queue ID
		expect(screen.getByText("test-queue-id")).toBeInTheDocument();

		// Check that we have formatted dates
		const formattedDates = screen.getAllByText("over 1 year ago");
		expect(formattedDates.length).toBeGreaterThan(0);
	});

	it("renders status badge with correct status", () => {
		const mockQueue = createFakeWorkPoolQueue({
			status: "READY",
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Ready")).toBeInTheDocument();
	});

	it("renders status badge with PAUSED status", () => {
		const mockQueue = createFakeWorkPoolQueue({
			status: "PAUSED",
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Paused")).toBeInTheDocument();
	});

	it("renders status badge with NOT_READY status", () => {
		const mockQueue = createFakeWorkPoolQueue({
			status: "NOT_READY",
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
	});

	it("displays 'Unlimited' when concurrency_limit is null", () => {
		const mockQueue = createFakeWorkPoolQueue({
			concurrency_limit: null,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Unlimited")).toBeInTheDocument();
	});

	it("displays 'Never' when last_polled is null", () => {
		const mockQueue = createFakeWorkPoolQueue({
			last_polled: null,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Never")).toBeInTheDocument();
	});

	it("hides description field when description is null", () => {
		const mockQueue = createFakeWorkPoolQueue({
			description: null,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		// Description label should not be present when description is null
		expect(screen.queryByText("Description")).not.toBeInTheDocument();
	});

	it("handles alternate layout properly", () => {
		const mockQueue = createFakeWorkPoolQueue();

		const { container } = render(
			<WorkPoolQueueDetails
				workPoolName="test-work-pool"
				queue={mockQueue}
				alternate={true}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("space-y-4");
	});

	it("applies default layout", () => {
		const mockQueue = createFakeWorkPoolQueue();

		const { container } = render(
			<WorkPoolQueueDetails
				workPoolName="test-work-pool"
				queue={mockQueue}
				alternate={false}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("space-y-6");
	});

	it("applies custom className", () => {
		const mockQueue = createFakeWorkPoolQueue();

		const { container } = render(
			<WorkPoolQueueDetails
				workPoolName="test-work-pool"
				queue={mockQueue}
				className="custom-class"
			/>,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("renders all field labels correctly", () => {
		const mockQueue = createFakeWorkPoolQueue({
			description: "Test description",
			priority: 1,
			concurrency_limit: 10,
			created: overOneYearAgo,
			updated: overOneYearAgo,
			last_polled: overOneYearAgo,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Work Pool")).toBeInTheDocument();
		expect(screen.getByText("Status")).toBeInTheDocument();
		expect(screen.getByText("Last Polled")).toBeInTheDocument();
		expect(screen.getByText("Description")).toBeInTheDocument();
		expect(screen.getByText("Priority")).toBeInTheDocument();
		expect(screen.getByText("Work Queue ID")).toBeInTheDocument();
		expect(screen.getByText("Flow Run Concurrency")).toBeInTheDocument();
		expect(screen.getByText("Created")).toBeInTheDocument();
		expect(screen.getByText("Last Updated")).toBeInTheDocument();
	});

	it("displays 'None' for missing optional fields", () => {
		const mockQueue = createFakeWorkPoolQueue({
			priority: undefined,
			created: undefined,
			updated: undefined,
		});

		render(
			<WorkPoolQueueDetails workPoolName="test-work-pool" queue={mockQueue} />,
			{ wrapper: createWrapper() },
		);

		// Should show "None" for null priority, created, and updated
		const noneElements = screen.getAllByText("None");
		expect(noneElements.length).toBeGreaterThanOrEqual(1);
	});
});
