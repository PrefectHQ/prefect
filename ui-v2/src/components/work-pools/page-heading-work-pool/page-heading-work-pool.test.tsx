import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PageHeadingWorkPool } from "./page-heading-work-pool";

// Mock Tanstack Router Link
vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
			<a href={to}>{children}</a>
		),
	};
});

// Mock the sub-components
vi.mock("@/components/work-pools/work-pool-toggle", () => ({
	WorkPoolToggle: ({ workPool }: { workPool: WorkPool }) => (
		<div data-testid="work-pool-toggle">Toggle for {workPool.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-menu", () => ({
	WorkPoolMenu: ({ workPool }: { workPool: WorkPool }) => (
		<div data-testid="work-pool-menu">Menu for {workPool.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-status-badge", () => ({
	WorkPoolStatusBadge: ({ status }: { status: string }) => (
		<div data-testid="work-pool-status-badge">{status}</div>
	),
}));

const mockWorkPool: WorkPool = {
	id: "123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "test-work-pool",
	description: "Test work pool",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: null,
	status: "READY",
};

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	const rootRoute = createRootRoute();
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory(),
	});

	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<RouterProvider router={router} />
			<TooltipProvider>{children}</TooltipProvider>
		</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("PageHeadingWorkPool", () => {
	it("renders breadcrumbs correctly", () => {
		const Wrapper = createWrapper();
		render(<PageHeadingWorkPool workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText(mockWorkPool.name)).toBeInTheDocument();
	});

	it("displays work pool title and status", () => {
		const Wrapper = createWrapper();
		render(<PageHeadingWorkPool workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByText(mockWorkPool.name)).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-status-badge")).toBeInTheDocument();
	});

	it("shows actions components", () => {
		const Wrapper = createWrapper();
		render(<PageHeadingWorkPool workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByTestId("work-pool-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-menu")).toBeInTheDocument();
	});

	it("passes onUpdate callback to actions", () => {
		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(
			<PageHeadingWorkPool workPool={mockWorkPool} onUpdate={onUpdate} />,
			{
				wrapper: Wrapper,
			},
		);
		expect(screen.getByTestId("work-pool-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-menu")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const Wrapper = createWrapper();
		const { container } = render(
			<PageHeadingWorkPool workPool={mockWorkPool} className="custom-class" />,
			{
				wrapper: Wrapper,
			},
		);
		expect(container.querySelector(".custom-class")).toBeInTheDocument();
	});
});
