import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueuePageHeader } from "./work-pool-queue-page-header";

// Mock Tanstack Router
vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		Link: ({
			children,
			to,
			params,
		}: {
			children: React.ReactNode;
			to: string;
			params?: Record<string, string>;
		}) => {
			const href = params
				? to.replace("$workPoolName", params.workPoolName || "")
				: to;
			return <a href={href}>{children}</a>;
		},
		useNavigate: () => vi.fn(),
		createLink:
			() =>
			({
				children,
				to,
				params,
			}: {
				children: React.ReactNode;
				to: string;
				params?: Record<string, string>;
			}) => {
				const href = params
					? to.replace("$workPoolName", params.workPoolName || "")
					: to;
				return <a href={href}>{children}</a>;
			},
	};
});

// Mock the sub-components
vi.mock("@/components/work-pools/work-pool-queue-toggle", () => ({
	WorkPoolQueueToggle: ({ queue }: { queue: WorkPoolQueue }) => (
		<div data-testid="work-pool-queue-toggle">Toggle for {queue.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-queue-menu", () => ({
	WorkPoolQueueMenu: ({ queue }: { queue: WorkPoolQueue }) => (
		<div data-testid="work-pool-queue-menu">Menu for {queue.name}</div>
	),
}));

const mockQueue = createFakeWorkPoolQueue({
	name: "test-queue",
	work_pool_name: "test-work-pool",
	status: "READY",
});

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<TooltipProvider>{children}</TooltipProvider>
		</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolQueuePageHeader", () => {
	it("renders breadcrumbs correctly", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueuePageHeader
				workPoolName="test-work-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: Wrapper,
			},
		);
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText("test-work-pool")).toBeInTheDocument();
		// Check that the queue name appears in the breadcrumb
		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toHaveTextContent(mockQueue.name);
	});

	it("displays queue name in breadcrumb", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueuePageHeader
				workPoolName="test-work-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: Wrapper,
			},
		);
		// Check the queue name appears in the breadcrumb page
		expect(screen.getByText(mockQueue.name)).toBeInTheDocument();
	});

	it("shows actions components", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueuePageHeader
				workPoolName="test-work-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: Wrapper,
			},
		);
		expect(screen.getByTestId("work-pool-queue-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-queue-menu")).toBeInTheDocument();
	});

	it("passes onUpdate callback to actions", () => {
		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueuePageHeader
				workPoolName="test-work-pool"
				queue={mockQueue}
				onUpdate={onUpdate}
			/>,
			{
				wrapper: Wrapper,
			},
		);
		expect(screen.getByTestId("work-pool-queue-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-queue-menu")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const Wrapper = createWrapper();
		const { container } = render(
			<WorkPoolQueuePageHeader
				workPoolName="test-work-pool"
				queue={mockQueue}
				className="custom-class"
			/>,
			{
				wrapper: Wrapper,
			},
		);
		expect(container.querySelector(".custom-class")).toBeInTheDocument();
	});

	it("renders correct breadcrumb links", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueuePageHeader
				workPoolName="my-pool"
				queue={createFakeWorkPoolQueue({
					name: "my-queue",
					work_pool_name: "my-pool",
				})}
			/>,
			{
				wrapper: Wrapper,
			},
		);

		// Check the Work Pools link
		const workPoolsLink = screen.getByText("Work Pools").closest("a");
		expect(workPoolsLink).toHaveAttribute("href", "/work-pools");

		// Check the work pool name link
		const workPoolLink = screen.getByText("my-pool").closest("a");
		expect(workPoolLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool",
		);
	});
});
